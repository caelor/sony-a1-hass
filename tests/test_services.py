"""Tests for Sony A1 Bus transmit service."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import (
    CONF_MAX_RETRIES,
    DOMAIN,
    SERVICE_DATA,
)


async def test_transmit_routes_to_correct_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    mock_esphome_service: AsyncMock,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test transmit service routes to correct ESPHome device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    device_registry = dr.async_get(hass)
    
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
    
    # Get the bridge device from registry
    sensor_device = device_registry.async_get_device_by_identifier(
        config_entry_id=mock_config_entry.entry_id,
        identifier=(DOMAIN, "test_node"),
    )
    assert sensor_device is not None
    
    await hass.services.async_call(
        DOMAIN,
        "transmit",
        {
            ATTR_DEVICE_ID: sensor_device.id,
            SERVICE_DATA: [0x12, 0x34],
            CONF_MAX_RETRIES: 2,
        },
        blocking=True,
    )
    
    mock_esphome_service.assert_called_once()
    call = mock_esphome_service.call_args[0][0]
    assert call.data[SERVICE_DATA] == [0x12, 0x34]
    assert call.data[CONF_MAX_RETRIES] == 2


async def test_transmit_fails_when_bridge_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test transmit service fails gracefully when bridge not found."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Call transmit service with non-existent device
    await hass.services.async_call(
        DOMAIN,
        "transmit",
        {
            ATTR_DEVICE_ID: "nonexistent_device_id",
            SERVICE_DATA: [0x12, 0x34],
            CONF_MAX_RETRIES: 0,
        },
        blocking=True,
    )
    
    # Verify error was logged
    assert "bridge device nonexistent_device_id not found" in caplog.text


async def test_transmit_schema_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test transmit service schema validation."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Test data out of range
    with pytest.raises(Exception):  # voluptuous will raise
        await hass.services.async_call(
            DOMAIN,
            "transmit",
            {
                ATTR_DEVICE_ID: "test_device",
                SERVICE_DATA: [256],  # Out of range
                CONF_MAX_RETRIES: 0,
            },
            blocking=True,
        )
    
    # Test negative data
    with pytest.raises(Exception):
        await hass.services.async_call(
            DOMAIN,
            "transmit",
            {
                ATTR_DEVICE_ID: "test_device",
                SERVICE_DATA: [-1],  # Negative
                CONF_MAX_RETRIES: 0,
            },
            blocking=True,
        )
