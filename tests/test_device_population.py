"""Tests for device availability tracking and population."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN, DeviceType


async def test_scan_known_devices_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that known devices are scanned on startup."""
    # Add config entry first
    mock_config_entry.add_to_hass(hass)
    
    # Create a mock ESPHome config entry
    esphome_config_entry = MockConfigEntry(
        domain="esphome",
        data={"device_name": "test_node"},
    )
    esphome_config_entry.add_to_hass(hass)
    
    # Create ESPHome bridge device
    esphome_device = device_registry.async_get_or_create(
        config_entry_id=esphome_config_entry.entry_id,
        identifiers={("esphome", "test_node")},
        name="Test ESPHome",
    )
    
    # Create bus bridge device (via ESPHome device)
    bridge_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node")},
        name="Sony A1 Bus Bridge",
        via_device_id=esphome_device.id,
    )
    
    # Create known bus devices
    cd_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node_90_0")},  # CD player, sub 0
        name="CD-0",
        via_device_id=bridge_device.id,
    )
    
    md_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node_b0_1")},  # MD player, sub 1
        name="MD-1",
        via_device_id=bridge_device.id,
    )
    
    # Set up integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Check that known devices were scanned
    known_devices = hass.data[DOMAIN][mock_config_entry.entry_id]["known_devices"]
    assert "test_node" in known_devices
    
    devices = known_devices["test_node"]
    assert len(devices) == 2
    
    # Check device types and sub-indices
    device_set = {(dt, si) for dt, si in devices}
    assert (DeviceType.CD_PLAYER, 0) in device_set
    assert (DeviceType.MD_RECORDER, 1) in device_set


async def test_ensure_bridge_exists_creates_bridge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that _async_ensure_bridge_exists creates bridge and returns was_created=True."""
    # Add config entry first
    mock_config_entry.add_to_hass(hass)
    
    # Create a mock ESPHome config entry
    esphome_config_entry = MockConfigEntry(
        domain="esphome",
        data={"device_name": "test_node"},
    )
    esphome_config_entry.add_to_hass(hass)
    
    # Create ESPHome bridge device
    esphome_device = device_registry.async_get_or_create(
        config_entry_id=esphome_config_entry.entry_id,
        identifiers={("esphome", "test_node")},
        name="Test ESPHome",
    )
    
    # Set up integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Call _async_ensure_bridge_exists
    from custom_components.sony_a1_bus import _async_ensure_bridge_exists
    
    was_created, bridge = await _async_ensure_bridge_exists(
        hass, mock_config_entry, "test_node", esphome_device.id
    )
    
    # Check that bridge was created
    assert was_created is True
    assert bridge is not None
    assert bridge["node"] == "test_node"
    
    # Check that bridge is in bridges dict
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    assert esphome_device.id in bridges


async def test_ensure_bridge_exists_returns_existing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that _async_ensure_bridge_exists returns was_created=False for existing bridge."""
    # Add config entry first
    mock_config_entry.add_to_hass(hass)
    
    # Create a mock ESPHome config entry
    esphome_config_entry = MockConfigEntry(
        domain="esphome",
        data={"device_name": "test_node"},
    )
    esphome_config_entry.add_to_hass(hass)
    
    # Create ESPHome bridge device
    esphome_device = device_registry.async_get_or_create(
        config_entry_id=esphome_config_entry.entry_id,
        identifiers={("esphome", "test_node")},
        name="Test ESPHome",
    )
    
    # Set up integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    from custom_components.sony_a1_bus import _async_ensure_bridge_exists
    
    # First call creates the bridge
    was_created1, bridge1 = await _async_ensure_bridge_exists(
        hass, mock_config_entry, "test_node", esphome_device.id
    )
    assert was_created1 is True
    
    # Second call should return existing bridge
    was_created2, bridge2 = await _async_ensure_bridge_exists(
        hass, mock_config_entry, "test_node", esphome_device.id
    )
    assert was_created2 is False
    assert bridge2 is bridge1


async def test_query_known_devices_sends_query_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that _async_query_known_devices sends query_status with delays."""
    # Add config entry first
    mock_config_entry.add_to_hass(hass)
    
    # Create a mock ESPHome config entry
    esphome_config_entry = MockConfigEntry(
        domain="esphome",
        data={"device_name": "test_node"},
    )
    esphome_config_entry.add_to_hass(hass)
    
    # Create ESPHome bridge device
    esphome_device = device_registry.async_get_or_create(
        config_entry_id=esphome_config_entry.entry_id,
        identifiers={("esphome", "test_node")},
        name="Test ESPHome",
    )
    
    # Create bus bridge device (via ESPHome device)
    bridge_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node")},
        name="Sony A1 Bus Bridge",
        via_device_id=esphome_device.id,
    )
    
    # Create known bus devices
    cd_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node_90_0")},
        name="CD-0",
        via_device_id=bridge_device.id,
    )
    
    # Set up integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Create bridge first
    from custom_components.sony_a1_bus import _async_ensure_bridge_exists, _async_query_known_devices
    await _async_ensure_bridge_exists(hass, mock_config_entry, "test_node", esphome_device.id)
    
    # Mock asyncio.sleep to avoid actual delays
    with patch("asyncio.sleep") as mock_sleep:
        await _async_query_known_devices(hass, mock_config_entry, "test_node", esphome_device.id)
        
        # Check that sleep was called with correct delays
        assert mock_sleep.call_count == 1  # 0.1s per device
        
        # Check delays
        calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert calls[0] == 0.1  # 100ms between queries
        
        # Check that player was created
        device_registries = hass.data[DOMAIN][mock_config_entry.entry_id]["device_registries"]
        assert bridge_device.id in device_registries
        
        player = device_registries[bridge_device.id].get_device(DeviceType.CD_PLAYER, 0)
        assert player is not None
        assert player.name == "CD-0"


async def test_query_known_devices_skips_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that _async_query_known_devices skips the specified device."""
    # Add config entry first
    mock_config_entry.add_to_hass(hass)
    
    # Create a mock ESPHome config entry
    esphome_config_entry = MockConfigEntry(
        domain="esphome",
        data={"device_name": "test_node"},
    )
    esphome_config_entry.add_to_hass(hass)
    
    # Create ESPHome bridge device
    esphome_device = device_registry.async_get_or_create(
        config_entry_id=esphome_config_entry.entry_id,
        identifiers={("esphome", "test_node")},
        name="Test ESPHome",
    )
    
    # Create bus bridge device (via ESPHome device)
    bridge_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node")},
        name="Sony A1 Bus Bridge",
        via_device_id=esphome_device.id,
    )
    
    # Create known bus devices
    cd_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node_90_0")},
        name="CD-0",
        via_device_id=bridge_device.id,
    )
    
    # Set up integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Create bridge first
    from custom_components.sony_a1_bus import _async_ensure_bridge_exists, _async_query_known_devices
    await _async_ensure_bridge_exists(hass, mock_config_entry, "test_node", esphome_device.id)
    
    # Mock asyncio.sleep to avoid actual delays
    with patch("asyncio.sleep") as mock_sleep:
        # Skip the CD player device
        await _async_query_known_devices(
            hass, mock_config_entry, "test_node", esphome_device.id,
            skip_device=(DeviceType.CD_PLAYER, 0)
        )
        
        # Check that sleep was NOT called (no devices queried)
        assert mock_sleep.call_count == 0


async def test_query_known_devices_creates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that _async_query_known_devices creates entities for known devices."""
    # Add config entry first
    mock_config_entry.add_to_hass(hass)
    
    # Create a mock ESPHome config entry
    esphome_config_entry = MockConfigEntry(
        domain="esphome",
        data={"device_name": "test_node"},
    )
    esphome_config_entry.add_to_hass(hass)
    
    # Create ESPHome bridge device
    esphome_device = device_registry.async_get_or_create(
        config_entry_id=esphome_config_entry.entry_id,
        identifiers={("esphome", "test_node")},
        name="Test ESPHome",
    )
    
    # Create bus bridge device (via ESPHome device)
    bridge_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node")},
        name="Sony A1 Bus Bridge",
        via_device_id=esphome_device.id,
    )
    
    # Create known bus device
    cd_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_node_90_0")},
        name="CD-0",
        via_device_id=bridge_device.id,
    )
    
    # Set up integration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Create bridge first
    from custom_components.sony_a1_bus import _async_ensure_bridge_exists, _async_query_known_devices
    await _async_ensure_bridge_exists(hass, mock_config_entry, "test_node", esphome_device.id)
    
    # Mock asyncio.sleep to avoid actual delays
    with patch("asyncio.sleep"):
        await _async_query_known_devices(hass, mock_config_entry, "test_node", esphome_device.id)
        await hass.async_block_till_done()
    
    # Check that entities were created
    entity_registry = er.async_get(hass)
    
    # Check media player
    media_player_entity = entity_registry.async_get("media_player.cd_0")
    assert media_player_entity is not None
    
    # Check sensors
    track_count_entity = entity_registry.async_get("sensor.cd_0_track_count")
    assert track_count_entity is not None
    
    disc_time_entity = entity_registry.async_get("sensor.cd_0_disc_time")
    assert disc_time_entity is not None
    
    input_source_entity = entity_registry.async_get("sensor.cd_0_input_source")
    assert input_source_entity is not None
    
    # Check binary sensor
    mono_entity = entity_registry.async_get("binary_sensor.cd_0_mono")
    assert mono_entity is not None
    
    # Check button
    query_status_entity = entity_registry.async_get("button.cd_0_query_status")
    assert query_status_entity is not None
