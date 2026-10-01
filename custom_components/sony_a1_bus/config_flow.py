"""Config flow for Sony A1 Bus integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_ENABLE_TIME_UPDATES,
    DEFAULT_ENABLE_TIME_UPDATES,
    DOMAIN,
)


class SonyA1BusOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Sony A1 Bus options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_TIME_UPDATES,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_TIME_UPDATES, DEFAULT_ENABLE_TIME_UPDATES
                        ),
                    ): bool,
                }
            ),
        )


class SonyA1BusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony A1 Bus."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SonyA1BusOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SonyA1BusOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title="Sony A1 Bus",
                data={},
                options={
                    CONF_ENABLE_TIME_UPDATES: DEFAULT_ENABLE_TIME_UPDATES,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
