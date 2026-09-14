"""Tests for Sony A1 Bus config flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sony_a1_bus.const import DOMAIN


async def test_user_step_creates_entry(hass: HomeAssistant) -> None:
    """Test user step creates entry successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sony A1 Bus"
    assert result["data"] == {}


async def test_user_step_duplicate_prevention(hass: HomeAssistant) -> None:
    """Test duplicate config entry is prevented."""
    # Add an existing entry with the same unique_id
    existing_entry = MockConfigEntry(
        domain=DOMAIN, 
        title="Sony A1 Bus", 
        data={},
        unique_id=DOMAIN,
    )
    existing_entry.add_to_hass(hass)
    
    # Try to create another entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
