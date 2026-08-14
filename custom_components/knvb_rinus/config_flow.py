from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientResponseError

from homeassistant import config_entries
from homeassistant.core import callback

from .client import RinusClient, RinusDataError
from .const import CONF_COOKIE, DOMAIN, NAME


COOKIE_HELP = (
    "Open Rinus in Chrome/Edge while logged in. Press F12 → Network, open a request "
    "to rinus.knvb.nl (for example 'profile'), choose Headers and find Request Headers → Cookie. "
    "Right-click the Cookie value and choose Copy value. Paste the COMPLETE Cookie header here. "
    "Do NOT copy Response Headers → Set-Cookie. The cookie is sensitive and must never be shared or committed to GitHub."
)


class RinusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE].strip()
            client = RinusClient(self.hass, {CONF_COOKIE: cookie})
            try:
                data = await client.async_fetch_all()
            except (RinusDataError, ClientResponseError):
                errors[CONF_COOKIE] = "invalid_auth"
            else:
                await self.async_set_unique_id(str(data.get("team", {}).get("id", "rinus")))
                self._abort_if_unique_id_configured()
                team_name = data.get("team", {}).get("teamName") or NAME
                return self.async_create_entry(
                    title=team_name,
                    data={CONF_COOKIE: cookie},
                )
            finally:
                await client.async_close()

        schema = vol.Schema({vol.Required(CONF_COOKIE): vol.All(str, vol.Length(min=10))})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors, description_placeholders={"cookie_help": COOKIE_HELP})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RinusOptionsFlow(config_entry)


class RinusOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.data.get(CONF_COOKIE, "")
        schema = vol.Schema({vol.Required(CONF_COOKIE, default=current): str})
        return self.async_show_form(step_id="init", data_schema=schema, description_placeholders={"cookie_help": COOKIE_HELP})
