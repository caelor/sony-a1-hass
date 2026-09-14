"""The Sony A1 Bus integration.

Bridges Sony Control-A1 (S-Link) bus messages between ESPHome devices and
Home Assistant. Discovers ESPHome devices that expose the sony_a1_bus
component by listening for their RX events on the HA event bus, creates a
diagnostic sensor per bridge, and exposes a service to transmit arbitrary
bus messages.

Also parses incoming bus messages to identify HiFi devices (CD players, MD
decks) and creates media_player and sensor entities for each.
"""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_DATA,
    ATTR_MUSICBRAINZ_ID,
    ATTR_TRUNCATED,
    CONF_MAX_RETRIES,
    DOMAIN,
    ESPHOME_DOMAIN,
    ESPHOME_SERVICE_TRANSMIT,
    EVENT_SONY_A1_BUS_HEARTBEAT,
    EVENT_SONY_A1_BUS_RX,
    SERVICE_DATA,
    SERVICE_SET_MUSICBRAINZ_ID,
    BridgeData,
    DeviceType,
)
from .coordinator import MetadataCoordinator
from .devices import DeviceRegistry, Player
from .protocol import decode_address, decode_message, get_codec_for_device_type

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.MEDIA_PLAYER, Platform.BUTTON, Platform.BINARY_SENSOR, Platform.SWITCH]

TRANSMIT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(SERVICE_DATA): vol.All(
            cv.ensure_list, [vol.All(int, vol.Range(min=0, max=255))]
        ),
        vol.Optional(CONF_MAX_RETRIES, default=0): vol.All(
            int, vol.Range(min=0, max=255)
        ),
    }
)


def _scan_known_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Scan device registry for known bus devices and group by bridge node name."""
    device_registry = dr.async_get(hass)
    known_devices: dict[str, list[tuple[DeviceType, int]]] = {}
    
    # Find all devices with our domain identifiers
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        # Bus equipment devices have via_device_id pointing to a bridge device.
        # Bridge devices have via_device_id pointing to ESPHome (which has no via_device_id).
        # Filter out non-equipment devices by checking the parent has a via_device_id.
        if device.via_device_id is None:
            continue
        
        bridge_device = device_registry.async_get(device.via_device_id)
        if bridge_device is None or bridge_device.via_device_id is None:
            continue
        
        esphome_device = device_registry.async_get(bridge_device.via_device_id)
        if esphome_device is None:
            continue
        
        node_name = None
        for entry_id in esphome_device.config_entries:
            esphome_entry = hass.config_entries.async_get_entry(entry_id)
            if esphome_entry and esphome_entry.domain == ESPHOME_DOMAIN:
                node_name = esphome_entry.data.get("device_name") or esphome_entry.title
                if node_name:
                    node_name = node_name.replace("-", "_")
                break
        
        if node_name is None:
            continue
        
        # Parse unique_id to extract device_type and sub_index
        # Format: {bridge_node}_{device_type:02x}_{sub_index}
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            
            # identifier is the unique_id
            parts = identifier.rsplit("_", 2)
            if len(parts) != 3:
                continue
            
            try:
                # Parse device_type as hex
                device_type_hex = parts[1]
                device_type = DeviceType(int(device_type_hex, 16))
                sub_index = int(parts[2])
                
                # Group by node_name
                if node_name not in known_devices:
                    known_devices[node_name] = []
                known_devices[node_name].append((device_type, sub_index))
                
                _LOGGER.debug(
                    "Found known device %s (type=%s, sub=%d) for bridge %s",
                    identifier,
                    device_type.name,
                    sub_index,
                    node_name,
                )
            except (ValueError, IndexError) as ex:
                _LOGGER.warning("Failed to parse device identifier %s: %s", identifier, ex)
    
    # Store known devices
    hass.data[DOMAIN][entry.entry_id]["known_devices"] = known_devices
    _LOGGER.info("Found %d bridge(s) with known devices", len(known_devices))


async def _async_ensure_bridge_exists(
    hass: HomeAssistant,
    entry: ConfigEntry,
    node_name: str,
    esphome_device_id: str,
) -> tuple[bool, BridgeData]:
    """Ensure bridge device exists, creating it if needed.
    
    Returns:
        Tuple of (was_created, bridge) where was_created is True if bridge was just created
    """
    bridges = hass.data[DOMAIN][entry.entry_id]["bridges"]
    
    if esphome_device_id in bridges:
        return False, bridges[esphome_device_id]
    
    device_registry = dr.async_get(hass)
    
    bridge_device_kwargs = {
        "config_entry_id": entry.entry_id,
        "identifiers": {(DOMAIN, node_name)},
        "name": f"Sony A1 Bus ({node_name})",
        "manufacturer": "Sony",
        "model": "Control-A1 Bridge",
        "via_device_id": esphome_device_id,
    }
    
    bridge_device = device_registry.async_get_or_create(**bridge_device_kwargs)
    bridge_device_id = bridge_device.id
    
    bridge: BridgeData = {
        "device_id": bridge_device_id,
        "node": node_name,
        "last_message": "",
        "truncated": False,
        "sensor": None,
        "bridge_version": "unknown",
    }
    bridges[esphome_device_id] = bridge
    
    # Create bridge sensor
    from .sensor import async_add_sensor_for_bridge
    async_add_sensor_for_bridge(hass, entry, bridge)
    
    return True, bridge


async def _async_query_known_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    node_name: str,
    esphome_device_id: str,
    skip_device: tuple[DeviceType, int] | None = None,
) -> None:
    """Query known devices for a bridge to discover their state.
    
    Args:
        skip_device: Optional tuple of (device_type, sub_index) to skip querying
    """
    bridges = hass.data[DOMAIN][entry.entry_id]["bridges"]
    bridge = bridges.get(esphome_device_id)
    if bridge is None:
        return
    
    bridge_device_id = bridge["device_id"]
    
    # Get known devices for this bridge
    known_devices = hass.data[DOMAIN][entry.entry_id]["known_devices"]
    devices = known_devices.get(node_name, [])
    
    if not devices:
        _LOGGER.debug("No known devices for bridge %s", node_name)
        return
    
    # Get or create device registry for this bridge
    device_registries = hass.data[DOMAIN][entry.entry_id]["device_registries"]
    if bridge_device_id not in device_registries:
        device_registries[bridge_device_id] = DeviceRegistry(
            hass=hass,
            bridge_node=bridge["node"],
            bridge_device_id=bridge_device_id,
        )
        
        # Create send callback for this bridge
        async def _send_to_bridge(data: bytes) -> bool:
            """Send data to the bus via this bridge."""
            try:
                service_name = f"{bridge['node']}_{ESPHOME_SERVICE_TRANSMIT}"
                await hass.services.async_call(
                    ESPHOME_DOMAIN,
                    service_name,
                    {SERVICE_DATA: list(data), CONF_MAX_RETRIES: 0},
                    blocking=True,
                )
                return True
            except Exception as ex:
                _LOGGER.error("Failed to send command via %s: %s", bridge['node'], ex)
                return False
        
        device_registries[bridge_device_id].set_send_callback(_send_to_bridge)
    
    device_registry = device_registries[bridge_device_id]
    
    # Create players and query devices
    for device_type, sub_index in devices:
        # Skip the device that triggered bridge creation (if specified)
        if skip_device is not None and (device_type, sub_index) == skip_device:
            _LOGGER.debug("Skipping query for trigger device %s", f"{device_type.name}-{sub_index}")
            continue
        
        from .const import DeviceType as DT
        from .protocol import AddressInfo
        
        # Create address info for this device
        address_info = AddressInfo(
            device_type=device_type,
            sub_index=sub_index,
            direction_from_device=True,
            canonical_address=(device_type & 0xF0) | sub_index,
        )
        
        # Get or create player
        player = device_registry.get_or_create_device(address_info)
        if player is None:
            continue
        
        # Ensure TOC callback is set before handling any messages
        _ensure_toc_callback_set(hass, entry, player)
        
        # Create entities if needed
        if player.media_player is None:
            await _async_create_entities_for_player(hass, entry, player)
        
        # Send query_status with 100ms delay
        _LOGGER.debug("Sending query_status to %s", player.name)
        await player.async_query_status()
        await asyncio.sleep(0.1)  # 100ms delay between queries


def _ensure_toc_callback_set(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player: Player,
) -> None:
    """Ensure the TOC complete callback is set on a player."""
    if player._toc_complete_callback is not None:
        return
    coordinator: MetadataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    player.set_toc_complete_callback(
        lambda p=player: coordinator.async_on_toc_complete(p)
    )


async def _async_create_entities_for_player(
    hass: HomeAssistant,
    entry: ConfigEntry,
    player,
) -> None:
    """Create entities for a player device."""
    from .binary_sensor import async_add_binary_sensors_for_device
    from .button import async_add_button_for_device
    from .media_player import async_add_media_player_for_device
    from .sensor import async_add_sensors_for_device
    from .switch import async_add_switch_for_device

    async_add_media_player_for_device(hass, entry, player)
    async_add_sensors_for_device(hass, entry, player)
    async_add_button_for_device(hass, entry, player)
    async_add_binary_sensors_for_device(hass, entry, player)

    coordinator: MetadataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_switch_for_device(hass, entry, player, coordinator)


def _find_player_by_device_id(hass: HomeAssistant, device_id: str) -> Player | None:
    """Find a player by its HA device ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        return None

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        for entry_data in hass.data[DOMAIN].values():
            for dev_registry in entry_data.get("device_registries", {}).values():
                for player in dev_registry.get_all_devices():
                    if player.unique_id == identifier:
                        return player
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sony A1 Bus from a config entry."""
    _LOGGER.debug("Sony A1 Bus integration setup from config entry")

    # Suppress musicbrainzngs INFO logs about uncaught XML attributes (type-id, first-release-date).
    # The library (v0.7.1) doesn't recognize newer MusicBrainz API fields, causing ~200 log messages per lookup.
    logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)

    coordinator = MetadataCoordinator(hass, entry)
    await coordinator.async_setup()

    # Initialize runtime data storage for this config entry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "bridges": {},  # device_id -> bridge data
        "device_registry": dr.async_get(hass),
        "async_add_entities": None,  # Will be set by sensor platform
        "async_add_media_players": None,  # Will be set by media_player platform
        "async_add_buttons": None,  # Will be set by button platform
        "async_add_binary_sensors": None,  # Will be set by binary_sensor platform
        "async_add_switches": None,  # Will be set by switch platform
        "device_registries": {},  # bridge_device_id -> DeviceRegistry
        "known_devices": {},  # bridge_device_id -> list of (device_type, sub_index)
        "coordinator": coordinator,
    }
    
    # Forward setup to platforms (this properly initializes entity platforms)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    
    _LOGGER.debug("Sony A1 Bus platforms loaded")
    
    # Get device registry for this entry
    device_registry = hass.data[DOMAIN][entry.entry_id]["device_registry"]
    
    # Scan device registry for known devices
    _scan_known_devices(hass, entry)
    
    @callback
    def _get_or_create_device_registry(
        bridge: BridgeData,
    ) -> DeviceRegistry:
        """Get or create a DeviceRegistry for a bridge."""
        device_registries = hass.data[DOMAIN][entry.entry_id]["device_registries"]
        bridge_device_id = bridge["device_id"]
        
        if bridge_device_id not in device_registries:
            device_registries[bridge_device_id] = DeviceRegistry(
                hass=hass,
                bridge_node=bridge["node"],
                bridge_device_id=bridge_device_id,
            )
            
            # Create send callback for this bridge
            async def _send_to_bridge(data: bytes) -> bool:
                """Send data to the bus via this bridge."""
                try:
                    service_name = f"{bridge['node']}_{ESPHOME_SERVICE_TRANSMIT}"
                    await hass.services.async_call(
                        ESPHOME_DOMAIN,
                        service_name,
                        {SERVICE_DATA: list(data), CONF_MAX_RETRIES: 0},
                        blocking=True,
                    )
                    return True
                except Exception as ex:
                    _LOGGER.error("Failed to send command via %s: %s", bridge['node'], ex)
                    return False
            
            device_registries[bridge_device_id].set_send_callback(_send_to_bridge)
        
        return device_registries[bridge_device_id]

    async def _handle_rx_event(event: Event) -> None:
        """Handle an incoming sony_a1_bus_rx event from an ESPHome device."""
        _LOGGER.debug("Received event: %s with data: %s", event.event_type, event.data)

        device_id: str | None = event.data.get(ATTR_DEVICE_ID)
        if device_id is None:
            _LOGGER.warning("Event missing ATTR_DEVICE_ID")
            return

        hex_data: str = event.data.get(ATTR_DATA, "")
        truncated: bool = event.data.get(ATTR_TRUNCATED) == "true"

        # Determine node_name from device_id
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if device is None:
            _LOGGER.warning("RX event from unknown device %s", device_id)
            return
        
        node_name = None
        for config_entry_id in device.config_entries:
            config_entry = hass.config_entries.async_get_entry(config_entry_id)
            if config_entry and config_entry.domain == ESPHOME_DOMAIN:
                node_name = config_entry.data.get("device_name") or config_entry.title
                if node_name:
                    node_name = node_name.replace("-", "_")
                break
        
        if node_name is None:
            _LOGGER.warning("Could not determine node name for device %s", device_id)
            return

        # Ensure bridge exists (create if needed)
        bridge_was_created, bridge = await _async_ensure_bridge_exists(
            hass, entry, node_name, device_id
        )
        
        bridge["last_message"] = hex_data
        bridge["truncated"] = truncated
        sensor = bridge.get("sensor")
        if sensor is not None:
            sensor.async_write_ha_state()

        # Parse the bus message and dispatch to device
        trigger_device = await _handle_bus_message(hass, entry, bridge, hex_data)
        
        # If bridge was just created, query other known devices (skip the trigger device)
        if bridge_was_created:
            skip_device = None
            if trigger_device is not None:
                skip_device = (trigger_device.device_type, trigger_device.sub_index)
            await _async_query_known_devices(
                hass, entry, node_name, device_id, skip_device=skip_device
            )

    async def _handle_bus_message(
        hass: HomeAssistant,
        entry: ConfigEntry,
        bridge: BridgeData,
        hex_data: str,
    ) -> Player | None:
        """Parse a bus message and dispatch to the appropriate device.
        
        Returns:
            The player that handled the message, or None if no player handled it
        """
        if not hex_data:
            return None

        # Convert hex string to bytes
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            _LOGGER.warning("Invalid hex data: %s", hex_data)
            return None

        if len(data) < 2:
            _LOGGER.debug("Message too short: %s", hex_data)
            return None

        # Decode address byte
        address_info = decode_address(data[0])
        
        # Get or create device registry for this bridge
        device_registry = _get_or_create_device_registry(bridge)
        
        # Get or create the device
        player = device_registry.get_or_create_device(address_info)
        if player is None:
            # Device type not supported or message is TO device (not FROM)
            return None

        # Ensure TOC callback is set before handling any messages
        _ensure_toc_callback_set(hass, entry, player)

        # Check if this is a newly created device (needs entities)
        is_new_device = player.media_player is None

        # Get codec for this device type
        codec = get_codec_for_device_type(address_info.device_type)
        
        # Decode the message
        message = decode_message(address_info, data, codec)
        if message is None:
            return None

        # Handle the message and get any commands to send back
        responses = player.handle_message(message)

        # Transmit any response commands sequentially
        if responses:
            _LOGGER.debug(
                "Queuing %d command(s) in response to message from %s",
                len(responses),
                player.name,
            )
            for cmd in responses:
                await player.async_send_command(cmd)

        # Create entities for newly discovered devices
        if is_new_device and player.media_player is None:
            await _async_create_entities_for_player(hass, entry, player)
        
        return player

    # Register event listener
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_SONY_A1_BUS_RX, _handle_rx_event)
    )
    _LOGGER.info("Sony A1 Bus event listener registered for %s", EVENT_SONY_A1_BUS_RX)

    # Register heartbeat event listener
    async def _handle_heartbeat_event(event: Event) -> None:
        """Handle heartbeat event from ESPHome bridge."""
        device_id: str | None = event.data.get(ATTR_DEVICE_ID)
        if device_id is None:
            _LOGGER.warning("Heartbeat event missing device_id")
            return
        
        bridge_version = event.data.get("bridge_version", "unknown")
        
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if device is None:
            _LOGGER.warning("Heartbeat from unknown device %s", device_id)
            return
        
        node_name = None
        for config_entry_id in device.config_entries:
            config_entry = hass.config_entries.async_get_entry(config_entry_id)
            if config_entry and config_entry.domain == ESPHOME_DOMAIN:
                node_name = config_entry.data.get("device_name") or config_entry.title
                if node_name:
                    node_name = node_name.replace("-", "_")
                break
        
        if node_name is None:
            _LOGGER.warning("Could not determine node name for device %s", device_id)
            return
        
        _LOGGER.debug(
            "Received heartbeat from bridge %s (version: %s)",
            node_name,
            bridge_version,
        )
        
        # Ensure bridge exists (create if needed)
        bridge_was_created, bridge = await _async_ensure_bridge_exists(
            hass, entry, node_name, device_id
        )
        
        # Update bridge version
        bridge["bridge_version"] = bridge_version
        
        # If bridge was just created, query all known devices
        if bridge_was_created:
            await _async_query_known_devices(hass, entry, node_name, device_id)
    
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_SONY_A1_BUS_HEARTBEAT, _handle_heartbeat_event)
    )
    _LOGGER.info("Sony A1 Bus heartbeat listener registered for %s", EVENT_SONY_A1_BUS_HEARTBEAT)

    # Register transmit service (only once)
    if not hass.services.has_service(DOMAIN, "transmit"):
        async def _async_handle_transmit(call: ServiceCall) -> None:
            """Forward a transmit request to the appropriate ESPHome device."""
            _LOGGER.debug("Transmit service called with data: %s", call.data)
            device_id: str = call.data[ATTR_DEVICE_ID]
            data: list[int] = call.data[SERVICE_DATA]
            max_retries: int = call.data[CONF_MAX_RETRIES]

            device_registry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)
            bridge_key: str | None = None
            if device_entry is not None:
                for config_entry_id in device_entry.config_entries:
                    config_entry = hass.config_entries.async_get_entry(config_entry_id)
                    if config_entry is None or config_entry.domain != DOMAIN:
                        continue
                    for domain, id_value in device_entry.identifiers:
                        if domain == DOMAIN:
                            bridge_key = id_value
                            break
                    if bridge_key is not None:
                        break

            if bridge_key is None:
                _LOGGER.error("Cannot transmit: bridge device %s not found", device_id)
                return

            bridge: BridgeData | None = None
            for entry_data in hass.data[DOMAIN].values():
                for bridge_device_id, bridge_data in entry_data["bridges"].items():
                    if bridge_data["node"] == bridge_key:
                        bridge = bridge_data
                        break
                if bridge is not None:
                    break

            if bridge is None:
                _LOGGER.error("Cannot transmit: bridge device %s not found", device_id)
                return

            node_name = bridge["node"]
            service_name = f"{node_name}_{ESPHOME_SERVICE_TRANSMIT}"
            _LOGGER.debug("Calling ESPHome service: %s", service_name)
            await hass.services.async_call(
                ESPHOME_DOMAIN,
                service_name,
                {SERVICE_DATA: data, CONF_MAX_RETRIES: max_retries},
                blocking=True,
            )

        hass.services.async_register(
            DOMAIN,
            "transmit",
            _async_handle_transmit,
            schema=TRANSMIT_SERVICE_SCHEMA,
        )
        _LOGGER.info("Sony A1 Bus transmit service registered")

    # Register set_musicbrainz_id service (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_SET_MUSICBRAINZ_ID):
        SET_MUSICBRAINZ_ID_SCHEMA = vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_MUSICBRAINZ_ID): cv.string,
            }
        )

        async def _async_handle_set_musicbrainz_id(call: ServiceCall) -> None:
            """Handle the set_musicbrainz_id service call."""
            device_id: str = call.data[ATTR_DEVICE_ID]
            mbid: str = call.data[ATTR_MUSICBRAINZ_ID]

            player = _find_player_by_device_id(hass, device_id)
            if player is None:
                _LOGGER.error("Cannot set MusicBrainz ID: player for device %s not found", device_id)
                return

            coordinator: MetadataCoordinator | None = None
            for entry_data in hass.data[DOMAIN].values():
                coordinator = entry_data.get("coordinator")
                if coordinator is not None:
                    break

            if coordinator is None:
                _LOGGER.error("Cannot set MusicBrainz ID: coordinator not found")
                return

            await coordinator.async_set_musicbrainz_id(player, mbid)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_MUSICBRAINZ_ID,
            _async_handle_set_musicbrainz_id,
            schema=SET_MUSICBRAINZ_ID_SCHEMA,
        )
        _LOGGER.info("Sony A1 Bus set_musicbrainz_id service registered")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Sony A1 Bus config entry")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Remove this entry's data
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove service if no more entries
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "transmit")
            hass.services.async_remove(DOMAIN, SERVICE_SET_MUSICBRAINZ_ID)
            _LOGGER.debug("Sony A1 Bus services removed")
    
    return unload_ok
