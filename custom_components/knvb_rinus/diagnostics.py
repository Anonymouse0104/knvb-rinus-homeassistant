from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_SENSITIVE_KEYS = {
    "cookie", "cookies", "set-cookie", "session", "session_cookie", "auth_cookie",
    "craftsessionid", "rinus_csrf", "csrf", "token", "access_token", "refresh_token",
    "authorization", "password",
}


def _redact(value: Any, key: str | None = None) -> Any:
    if key and key.lower().replace("_", "-") in _SENSITIVE_KEYS:
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")
    payload = coordinator.data if coordinator else {}
    safe_payload = _redact(payload)

    return {
        "integration_version": VERSION,
        "config_entry_id": entry.entry_id,
        "last_update_success": coordinator.last_update_success if coordinator else False,
        "update_interval_seconds": int(coordinator.update_interval.total_seconds()) if coordinator else None,
        "data": safe_payload,
    }
