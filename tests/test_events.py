"""Tests for Sony A1 Bus event handling."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN


async def test_rx_event_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RX event triggers bridge discovery."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Fire heartbeat event first to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()
    
    # Fire RX event
    fire_rx_event(mock_esphome_device.id, data="AABB", truncated="false")
    await hass.async_block_till_done()
    
    # Verify bridge was discovered
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    assert len(bridges) > 0
    assert "test_node" in caplog.text


async def test_rx_event_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test RX event updates existing bridge."""
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
    
    bridge = bridges[bridge_device_id]
    assert bridge["last_message"] == "AABB"
    assert bridge["truncated"] is False
    
    # Second RX event
    fire_rx_event(bridge_device_id, data="CCDD", truncated="true")
    await hass.async_block_till_done()
    
    assert bridge["last_message"] == "CCDD"
    assert bridge["truncated"] is True


async def test_rx_event_missing_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RX event with missing device_id logs warning."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Fire event without device_id
    hass.bus.async_fire(
        "esphome.sony_a1_bus_rx",
        {"data": "AABB", "truncated": "false"},
    )
    await hass.async_block_till_done()
    
    assert "Event missing ATTR_DEVICE_ID" in caplog.text


async def test_truncated_field_parsing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test truncated field is parsed correctly from string."""
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
    
    # Test truncated="true"
    fire_rx_event(bridge_device_id, data="AABB", truncated="true")
    await hass.async_block_till_done()
    
    bridge = bridges[bridge_device_id]
    assert bridge["truncated"] is True
    
    # Test truncated="false"
    fire_rx_event(bridge_device_id, data="CCDD", truncated="false")
    await hass.async_block_till_done()
    
    assert bridge["truncated"] is False
