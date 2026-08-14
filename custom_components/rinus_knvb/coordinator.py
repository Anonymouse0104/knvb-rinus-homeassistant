"""Data coordinator for KNVB Rinus."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RinusAuthError, RinusClient, RinusConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


class RinusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate one Rinus poll for all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        config_entry: ConfigEntry,
    ) -> None:
        self.client = RinusClient(session, config_entry.data["session_cookie"])
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and normalize calendar/team data."""
        try:
            calendar = await self.client.async_get_calendar()
            try:
                team_page = await self.client.async_get_team()
            except RinusAuthError:
                raise
            except RinusConnectionError:
                team_page = {}
        except RinusAuthError as err:
            raise err
        except RinusConnectionError as err:
            raise UpdateFailed(str(err)) from err

        return build_data(calendar, team_page)


def _event_from_item(item: dict[str, Any]) -> dict[str, Any] | None:
    event = item.get("event")
    if not isinstance(event, dict):
        return None
    result = dict(event)
    result["date"] = item.get("date")
    result["day"] = item.get("day")
    result["type"] = item.get("type")
    return result


def build_data(calendar: dict[str, Any], team_page: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw Rinus page props into stable Home Assistant data."""
    items = calendar.get("items") or []
    today_raw = calendar.get("today", {}).get("date")
    try:
        today = date.fromisoformat(today_raw)
    except (TypeError, ValueError):
        today = date.today()

    events: list[dict[str, Any]] = []
    for item in items:
        event = _event_from_item(item)
        if event:
            events.append(event)

    matches = [e for e in events if e.get("type") == "match" and e.get("matchDay")]
    matches.sort(key=lambda e: e.get("matchDay") or "")
    trainings = [e for e in events if e.get("type") == "training"]
    trainings.sort(key=lambda e: (e.get("date") or "", e.get("time") or ""))

    next_match = None
    last_match = None
    for event in matches:
        try:
            match_dt = datetime.fromisoformat(str(event["matchDay"]))
        except (KeyError, ValueError):
            continue
        if match_dt.date() >= today and next_match is None:
            next_match = event
        if match_dt.date() < today:
            last_match = event

    next_training = None
    for event in trainings:
        if event.get("date") and str(event["date"]) >= today.isoformat():
            next_training = event
            break

    team = team_page.get("team") if isinstance(team_page, dict) else None
    if not isinstance(team, dict):
        team = {}

    return {
        "season": calendar.get("season", {}),
        "today": calendar.get("today", {}),
        "calendar_items": items,
        "events": events,
        "matches": matches,
        "trainings": trainings,
        "next_match": next_match,
        "last_match": last_match,
        "next_training": next_training,
        "team": team,
        "active_team": calendar.get("activeTeam", {}),
    }
