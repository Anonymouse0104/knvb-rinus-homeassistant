from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")
    payload = coordinator.data if coordinator else {}
    payload = payload if isinstance(payload, dict) else {}

    # Never expose the configured Rinus cookie/session in diagnostics.
    safe = dict(payload)
    safe.pop("cookie", None)
    safe.pop("cookies", None)
    safe.pop("session_cookie", None)
    safe.pop("auth_cookie", None)
    safe.pop("session", None)

    team = safe.get("team")
    if isinstance(team, dict):
        safe["team"] = dict(team)
        safe["team"].pop("cookie", None)

    return {
        "integration_version": VERSION,
        "config_entry_id": entry.entry_id,
        "data": safe,
    }
