"""Config flow for KNVB Rinus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RinusAuthError, RinusClient, RinusConnectionError
from .const import CONF_SESSION_COOKIE, DOMAIN


class RinusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a KNVB Rinus config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user setup step."""
        errors: dict[str, str] = {}
        if user_input:
            cookie = user_input[CONF_SESSION_COOKIE].strip()
            try:
                client = RinusClient(async_get_clientsession(self.hass), cookie)
                data = await client.async_validate()
            except RinusAuthError:
                errors["base"] = "invalid_session"
            except RinusConnectionError:
                errors["base"] = "cannot_connect"
            else:
                team_name = "KNVB Rinus"
                active = data.get("activeTeam")
                if isinstance(active, dict):
                    team_name = active.get("teamName") or active.get("title") or team_name
                await self.async_set_unique_id(f"rinus_{team_name}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=team_name,
                    data={CONF_SESSION_COOKIE: cookie},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_SESSION_COOKIE): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle session reauthentication."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                client = RinusClient(
                    async_get_clientsession(self.hass),
                    user_input[CONF_SESSION_COOKIE].strip(),
                )
                data = await client.async_validate()
            except RinusAuthError:
                errors["base"] = "invalid_session"
            except RinusConnectionError:
                errors["base"] = "cannot_connect"
            else:
                active = data.get("activeTeam")
                title = "KNVB Rinus"
                if isinstance(active, dict):
                    title = active.get("teamName") or active.get("title") or title
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_SESSION_COOKIE: user_input[CONF_SESSION_COOKIE].strip()},
                    title=title,
                )

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_SESSION_COOKIE): str}),
            errors=errors,
        )
