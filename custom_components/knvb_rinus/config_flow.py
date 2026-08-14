from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientResponseError

from homeassistant import config_entries
from homeassistant.core import callback

from .client import RinusClient, RinusDataError
from .const import CONF_COOKIE, DEFAULT_SCAN_INTERVAL, DOMAIN, NAME


COOKIE_HELP = (
    "Open Rinus in Chrome/Edge while logged in. Press F12 → Network. Open a request to "
    "rinus.knvb.nl (for example **team.json** or **profile**), choose **Headers**, scroll to "
    "**Request Headers** and find **Cookie**. Right-click the Cookie value and choose "
    "**Copy value**. Paste the COMPLETE Cookie request-header here. **Do not use Response "
    "Headers → Set-Cookie.** The Cookie is sensitive authentication information and must "
    "never be shared."
)


def _schema(default_cookie: str | None = None):
    cookie_field = vol.Required(CONF_COOKIE)
    if default_cookie:
        cookie_field = vol.Required(CONF_COOKIE, default=default_cookie)
    return vol.Schema({cookie_field: vol.All(str, vol.Length(min=10))})


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
                team_id = str(data.get("team", {}).get("id") or "rinus")
                await self.async_set_unique_id(team_id)
                self._abort_if_unique_id_configured()
                team_name = data.get("team", {}).get("teamName") or NAME
                return self.async_create_entry(
                    title=team_name,
                    data={CONF_COOKIE: cookie},
                    options={"scan_interval": DEFAULT_SCAN_INTERVAL},
                )
            finally:
                await client.async_close()

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(),
            errors=errors,
            description_placeholders={"cookie_help": COOKIE_HELP},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RinusOptionsFlow(config_entry)


class RinusOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            cookie = user_input[CONF_COOKIE].strip()
            client = RinusClient(self.hass, {CONF_COOKIE: cookie})
            try:
                await client.async_fetch_all()
            except (RinusDataError, ClientResponseError):
                errors[CONF_COOKIE] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_COOKIE: cookie,
                        "scan_interval": user_input.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                    },
                )
            finally:
                await client.async_close()

        current_cookie = self.config_entry.data.get(CONF_COOKIE, "")
        current_interval = self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_COOKIE, default=current_cookie): vol.All(str, vol.Length(min=10)),
                vol.Required("scan_interval", default=current_interval): vol.All(
                    vol.Coerce(int), vol.In([300, 600, 900, 1800, 3600])
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"cookie_help": COOKIE_HELP},
        )
