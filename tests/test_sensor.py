"""Tests for Sony A1 Bus sensor platform."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN


async def test_sensor_created_on_first_rx(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test sensor entity is created on first RX event."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()
    
    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None
    
    # Fire RX event to trigger bridge discovery
    fire_rx_event(bridge_device_id, data="AABB", truncated="false")
    await hass.async_block_till_done()
    
    # Verify sensor entity was created
    entity_id = f"sensor.sony_a1_bus_test_node_last_bus_message"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "AABB"


async def test_sensor_state_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test sensor state updates on subsequent RX events."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()
    
    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None
    
    # First RX event
    fire_rx_event(bridge_device_id, data="AABB", truncated="false")
    await hass.async_block_till_done()
    
    entity_id = f"sensor.sony_a1_bus_test_node_last_bus_message"
    state = hass.states.get(entity_id)
    assert state.state == "AABB"
    
    # Second RX event
    fire_rx_event(bridge_device_id, data="CCDD", truncated="false")
    await hass.async_block_till_done()
    
    state = hass.states.get(entity_id)
    assert state.state == "CCDD"


async def test_sensor_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test sensor attributes include node and truncated."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()
    
    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None
    
    # Fire RX event with truncated=true
    fire_rx_event(bridge_device_id, data="AABB", truncated="true")
    await hass.async_block_till_done()
    
    entity_id = f"sensor.sony_a1_bus_test_node_last_bus_message"
    state = hass.states.get(entity_id)
    
    assert state.attributes["node"] == "test_node"
    assert state.attributes["truncated"] is True


async def test_sensor_device_linkage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    device_registry: dr.DeviceRegistry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test sensor device is linked to ESPHome device via via_device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Fire heartbeat event to trigger bridge discovery
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()
    
    # Get the bridge device from registry using the new API
    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "test_node"),
        mock_config_entry.entry_id,
    )
    assert bridge_device is not None
    
    # Verify via_device points to ESPHome device
    assert bridge_device.via_device_id == mock_esphome_device.id


async def test_input_source_sensor_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test input source sensor is created for device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Fire RX event with status message (S3=0x01 for analog input)
    # Address: 0x98 = CD player, from device, sub 0
    # Command: 0x70 = status, S1=0x01 (playing), S2=0x00, S3=0x01 (analog), disc=0x01, track=0x01
    fire_rx_event(bridge_device_id, data="98700100010101", truncated="false")
    await hass.async_block_till_done()

    # Verify input source sensor was created
    entity_id = "sensor.cd_0_input_source"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Analog"


async def test_input_source_sensor_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test input source sensor updates when status changes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # First status with analog input (S3=0x01)
    fire_rx_event(bridge_device_id, data="98700100010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "sensor.cd_0_input_source"
    state = hass.states.get(entity_id)
    assert state.state == "Analog"

    # Second status with optical input (S3=0x03)
    fire_rx_event(bridge_device_id, data="98700100030101", truncated="false")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "Optical"


async def test_mono_sensor_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test mono binary sensor is created for device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Fire RX event with status message (S3=0x81 for analog input + mono)
    fire_rx_event(bridge_device_id, data="98700100810101", truncated="false")
    await hass.async_block_till_done()

    # Verify mono sensor was created
    entity_id = "binary_sensor.cd_0_mono"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_mono_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test mono binary sensor shows off when mono flag is not set."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Fire RX event with status message (S3=0x01 for analog input, no mono)
    fire_rx_event(bridge_device_id, data="98700100010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_mono"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_power_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test power binary sensor shows on when device is powered."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with power on (S1=0x01, bit 4=0 means power on)
    fire_rx_event(bridge_device_id, data="98700100010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_power"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_power_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test power binary sensor shows off when device is powered off."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with power off (S1=0x11, bit 4=1 means power off)
    fire_rx_event(bridge_device_id, data="98701100010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_power"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_disc_loaded_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test disc loaded binary sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with disc loaded (S1=0x01, bit 5=0 means disc loaded)
    fire_rx_event(bridge_device_id, data="98700100010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_disc_loaded"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_shuffle_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test shuffle binary sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with shuffle on (S2=0x01, bit 0=1)
    fire_rx_event(bridge_device_id, data="98700101010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_shuffle"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_repeat_all_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test repeat all binary sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with repeat all on (S2=0x08, bit 3=1)
    fire_rx_event(bridge_device_id, data="98700108010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_repeat_all"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_repeat_one_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test repeat one binary sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with repeat one on (S2=0x10, bit 4=1)
    fire_rx_event(bridge_device_id, data="98700110010101", truncated="false")
    await hass.async_block_till_done()

    entity_id = "binary_sensor.cd_0_repeat_one"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_current_disc_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test current disc sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with disc loaded, disc 3
    fire_rx_event(bridge_device_id, data="98700100010301", truncated="false")
    await hass.async_block_till_done()

    entity_id = "sensor.cd_0_current_disc"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "3"


async def test_current_track_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test current track sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Status message with disc loaded, track 5
    fire_rx_event(bridge_device_id, data="98700100010105", truncated="false")
    await hass.async_block_till_done()

    entity_id = "sensor.cd_0_current_track"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"


async def test_current_track_time_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test current track time sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # First send a status to set disc_loaded=true
    fire_rx_event(bridge_device_id, data="98700100010101", truncated="false")
    await hass.async_block_till_done()

    # Track change message (0x50): disc=01, track=01, min=04, sec=32
    fire_rx_event(bridge_device_id, data="985001010432", truncated="false")
    await hass.async_block_till_done()

    entity_id = "sensor.cd_0_current_track_time"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "4:32"


async def test_device_capabilities_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test device capabilities sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Device capacity message (0x61): disc_count=01, capabilities=1F
    fire_rx_event(bridge_device_id, data="9861011F", truncated="false")
    await hass.async_block_till_done()

    entity_id = "sensor.cd_0_device_capabilities"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "31"


async def test_disc_count_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test disc count sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break

    assert bridge_device_id is not None

    # Device capacity message (0x61): disc_count=05, capabilities=1F
    fire_rx_event(bridge_device_id, data="9861051F", truncated="false")
    await hass.async_block_till_done()

    entity_id = "sensor.cd_0_disc_count"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"
