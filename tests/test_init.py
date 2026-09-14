"""Tests for Sony A1 Bus integration setup and unload."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN


async def test_setup_creates_hass_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup creates hass.data structure."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert "bridges" in hass.data[DOMAIN][mock_config_entry.entry_id]
    assert "device_registry" in hass.data[DOMAIN][mock_config_entry.entry_id]
    assert "async_add_entities" in hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_setup_failure_cleanup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure cleans up hass.data."""
    mock_config_entry.add_to_hass(hass)
    
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=Exception("Setup failed"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    
    # Verify the entry is in SETUP_ERROR state
    assert mock_config_entry.state.name == "SETUP_ERROR"
    # Verify cleanup - the entry should not be in hass.data
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_unload_removes_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload removes hass.data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_unload_removes_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload removes service when last entry unloaded."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Service should be registered
    assert hass.services.has_service(DOMAIN, "transmit")
    
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    
    # Service should be removed
    assert not hass.services.has_service(DOMAIN, "transmit")
