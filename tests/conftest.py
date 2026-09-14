"""Shared fixtures for Sony A1 Bus integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sony A1 Bus",
        data={},
        entry_id="test_entry_id",
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
    # Add the ESPHome config entry to hass
    mock_esphome_config_entry.add_to_hass(hass)
    
    # Create device with ESPHome identifiers
    device = device_registry.async_get_or_create(
        config_entry_id=mock_esphome_config_entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "test_node_mac")},
        name="test_node",
    )
    return device


@pytest.fixture
async def mock_esphome_service(hass: HomeAssistant) -> MagicMock:
    """Mock ESPHome service by registering a mock service."""
    from unittest.mock import MagicMock
    mock_call = MagicMock()
    
    async def mock_service_handler(call):
        mock_call(call)
    
    # Register the mock service
    hass.services.async_register(
        ESPHOME_DOMAIN,
        "test_node_transmit",
        mock_service_handler,
    )
    
    yield mock_call
    
    # Clean up
    hass.services.async_remove(ESPHOME_DOMAIN, "test_node_transmit")


@pytest.fixture
def fire_rx_event(hass: HomeAssistant):
    """Helper to fire sony_a1_bus_rx events."""
    def _fire(device_id: str, data: str = "1234", truncated: str = "false"):
        hass.bus.async_fire(
            EVENT_SONY_A1_BUS_RX,
            {
                "device_id": device_id,
                ATTR_DATA: data,
                ATTR_TRUNCATED: truncated,
            },
        )
    return _fire


@pytest.fixture
def fire_heartbeat_event(hass: HomeAssistant):
    """Helper to fire sony_a1_bus_heartbeat events."""
    def _fire(device_id: str, bridge_version: str = "1.0.0"):
        hass.bus.async_fire(
            EVENT_SONY_A1_BUS_HEARTBEAT,
            {
                "device_id": device_id,
                "bridge_version": bridge_version,
            },
        )
    return _fire
