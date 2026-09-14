"""Integration tests for bus device entity creation."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import (
    ATTR_DATA,
    ATTR_TRUNCATED,
    DOMAIN,
    ESPHOME_DOMAIN,
    EVENT_SONY_A1_BUS_RX,
    EVENT_SONY_A1_BUS_HEARTBEAT,
)


@pytest.fixture
def mock_esphome_config_entry() -> MockConfigEntry:
    """Create a mock ESPHome config entry."""
    return MockConfigEntry(
        domain=ESPHOME_DOMAIN,
        title="test_node",
        data={"device_name": "test_node"},
        entry_id="esphome_entry_id",
    )


@pytest.fixture
def mock_esphome_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_esphome_config_entry: MockConfigEntry,
) -> dr.DeviceEntry:
    """Create a mock ESPHome device in the registry."""
    mock_esphome_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_esphome_config_entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "test_node_mac")},
        name="test_node",
    )
    return device


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sony A1 Bus",
        data={},
        entry_id="test_entry_id",
    )


async def test_cd_player_device_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
) -> None:
    """Test that a CD player device is created when a message is received."""
    # Set up the integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire a heartbeat event to create the bridge
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_HEARTBEAT,
        {
            "device_id": mock_esphome_device.id,
            "bridge_version": "1.0.0",
        },
    )
    await hass.async_block_till_done()

    # Get the bridge device ID from the integration's data structure
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    assert len(bridges) > 0, "No bridges were created"
    
    # Find the bridge for test_node
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None, "Bridge device was not created"

    # Fire a status message from a CD player (0x98 = CD player, from device, sub 0)
    # Status: playing, disc 1, track 1
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_RX,
        {
            "device_id": bridge_device_id,
            ATTR_DATA: "98700100000101",  # 98 70 01 00 00 01 01
            ATTR_TRUNCATED: "false",
        },
    )
    await hass.async_block_till_done()

    # Verify that a device was created for the CD player
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    
    # Should have at least 2 devices: bridge + CD player
    assert len(devices) >= 2
    
    # Find the CD player device
    cd_player_device = None
    for device in devices:
        if device.name and "CD-0" in device.name:
            cd_player_device = device
            break
    
    assert cd_player_device is not None
    assert cd_player_device.manufacturer == "Sony"


async def test_md_player_device_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
) -> None:
    """Test that an MD player device is created when a message is received."""
    # Set up the integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire a heartbeat event to create the bridge
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_HEARTBEAT,
        {
            "device_id": mock_esphome_device.id,
            "bridge_version": "1.0.0",
        },
    )
    await hass.async_block_till_done()

    # Get the bridge device ID from the integration's data structure
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    assert len(bridges) > 0, "No bridges were created"
    
    # Find the bridge for test_node
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None, "Bridge device was not created"

    # Fire a status message from an MD player (0xB8 = MD player, from device, sub 0)
    # Status: playing, disc 1, track 1
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_RX,
        {
            "device_id": bridge_device_id,
            ATTR_DATA: "b8700100000101",  # b8 70 01 00 00 01 01
            ATTR_TRUNCATED: "false",
        },
    )
    await hass.async_block_till_done()

    # Verify that a device was created for the MD player
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    
    # Should have at least 2 devices: bridge + MD player
    assert len(devices) >= 2
    
    # Find the MD player device
    md_player_device = None
    for device in devices:
        if device.name and "MD-0" in device.name:
            md_player_device = device
            break
    
    assert md_player_device is not None
    assert md_player_device.manufacturer == "Sony"


async def test_multiple_devices_same_bridge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
) -> None:
    """Test that multiple devices can be created from the same bridge."""
    # Set up the integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire a heartbeat event to create the bridge
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_HEARTBEAT,
        {
            "device_id": mock_esphome_device.id,
            "bridge_version": "1.0.0",
        },
    )
    await hass.async_block_till_done()

    # Get the bridge device ID from the integration's data structure
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    assert len(bridges) > 0, "No bridges were created"
    
    # Find the bridge for test_node
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None, "Bridge device was not created"

    # Fire messages from a CD player and an MD player
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_RX,
        {
            "device_id": bridge_device_id,
            ATTR_DATA: "98700100000101",  # CD player
            ATTR_TRUNCATED: "false",
        },
    )
    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_RX,
        {
            "device_id": bridge_device_id,
            ATTR_DATA: "b8700100000101",  # MD player
            ATTR_TRUNCATED: "false",
        },
    )
    await hass.async_block_till_done()

    # Verify that both devices were created
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    
    # Should have at least 3 devices: bridge + CD player + MD player
    assert len(devices) >= 3
    
    # Find both player devices
    cd_player_device = None
    md_player_device = None
    for device in devices:
        if device.name and "CD-0" in device.name:
            cd_player_device = device
        elif device.name and "MD-0" in device.name:
            md_player_device = device
    
    assert cd_player_device is not None
    assert md_player_device is not None


async def test_bridge_only_one_device_with_no_hifi(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
) -> None:
    """Test that only one bridge device is created when no hifi devices are on the bus."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_HEARTBEAT,
        {
            "device_id": mock_esphome_device.id,
            "bridge_version": "1.0.0",
        },
    )
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(devices) == 1
    assert devices[0].name == "Sony A1 Bus (test_node)"
    assert devices[0].manufacturer == "Sony"
    assert devices[0].model == "Control-A1 Bridge"


async def test_device_name_updated_from_0x6a_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
) -> None:
    """Test that device name and model are updated when 0x6A device name message is received."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_HEARTBEAT,
        {
            "device_id": mock_esphome_device.id,
            "bridge_version": "1.0.0",
        },
    )
    await hass.async_block_till_done()

    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    assert bridge_device_id is not None

    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_RX,
        {
            "device_id": bridge_device_id,
            ATTR_DATA: "b8700100000101",
            ATTR_TRUNCATED: "false",
        },
    )
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    md_device = None
    for device in devices:
        if device.name and "MD-0" in device.name:
            md_device = device
            break
    assert md_device is not None
    assert md_device.model == "Unknown"

    hass.bus.async_fire(
        EVENT_SONY_A1_BUS_RX,
        {
            "device_id": bridge_device_id,
            ATTR_DATA: "b86a4d44532d4a45353330",
            ATTR_TRUNCATED: "false",
        },
    )
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    md_device = None
    for device in devices:
        if device.identifiers and (DOMAIN, "test_node_b0_0") in device.identifiers:
            md_device = device
            break
    assert md_device is not None
    assert md_device.name == "MDS-JE530"
    assert md_device.model == "MDS-JE530"
