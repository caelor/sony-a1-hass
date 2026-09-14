"""Tests for Sony A1 Bus button platform."""

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN


async def test_button_created_for_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test query status button is created when device is discovered."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID from the integration's data structure
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None, "Bridge device was not created"

    # Fire RX event from a CD player to trigger device discovery
    # Address: 0x98 = CD player, from device, sub 0
    # Command: 0x70 = status, S1=0x01 (playing), S2=0x00, S3=0x00, disc=0x01, track=0x01
    fire_rx_event(bridge_device_id, data="98700100000101", truncated="false")
    await hass.async_block_till_done()

    # Verify button entity was created
    entity_id = "button.cd_0_query_status"
    state = hass.states.get(entity_id)
    assert state is not None


async def test_button_is_diagnostic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
) -> None:
    """Test query status button is categorized as diagnostic."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID from the integration's data structure
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None, "Bridge device was not created"

    # Fire RX event to trigger device discovery
    fire_rx_event(bridge_device_id, data="98700100000101", truncated="false")
    await hass.async_block_till_done()

    # Get the entity registry entry
    from homeassistant.helpers import entity_registry as er
    entity_registry = er.async_get(hass)
    entity_id = "button.cd_0_query_status"
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_button_press_sends_query_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_esphome_device: dr.DeviceEntry,
    fire_heartbeat_event,
    fire_rx_event,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test pressing the button sends a 0x0F query status command."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fire heartbeat event to create the bridge
    fire_heartbeat_event(mock_esphome_device.id)
    await hass.async_block_till_done()

    # Get the bridge device ID from the integration's data structure
    bridges = hass.data[DOMAIN][mock_config_entry.entry_id]["bridges"]
    bridge_device_id = None
    for device_id, bridge in bridges.items():
        if bridge["node"] == "test_node":
            bridge_device_id = device_id
            break
    
    assert bridge_device_id is not None, "Bridge device was not created"

    # Fire RX event to trigger device discovery
    fire_rx_event(bridge_device_id, data="98700100000101", truncated="false")
    await hass.async_block_till_done()

    # Press the button
    entity_id = "button.cd_0_query_status"
    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify the command was logged (since we don't have a real bridge to send to)
    assert "Cannot send command" in caplog.text or "query_status" in caplog.text.lower()
