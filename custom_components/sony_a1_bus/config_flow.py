"""Config flow for Sony A1 Bus integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class SonyA1BusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony A1 Bus."""

    VERSION = 1

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
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
