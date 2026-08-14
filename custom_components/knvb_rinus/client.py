from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from datetime import date, datetime
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import BASE_URL, CALENDAR_PATHS, CONF_COOKIE, TEAM_PATHS

_LOGGER = logging.getLogger(__name__)


class RinusDataError(Exception):
    """Raised when Rinus data cannot be fetched or parsed."""


def _extract_next_data(text: str) -> dict[str, Any] | None:
    """Extract the Next.js __NEXT_DATA__ JSON payload from a Rinus page."""
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None

    raw = html.unescape(match.group(1).strip())
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as err:
        _LOGGER.debug("Kon __NEXT_DATA__ niet parsen: %s", err)
        return None

    return payload if isinstance(payload, dict) else None


def _page_props(text: str) -> dict[str, Any]:
    """Return Next.js pageProps from a Rinus HTML response."""
    payload = _extract_next_data(text) or {}
    props = payload.get("props")
    if not isinstance(props, dict):
        return {}
    page_props = props.get("pageProps")
    return page_props if isinstance(page_props, dict) else {}


def _extract_team(text: str) -> dict[str, Any]:
    """Extract the active team from the profile page payload."""
    page_props = _page_props(text)

    # On /profile/team the active team is located at pageProps.session.team.
    session = page_props.get("session")
    if isinstance(session, dict):
        team = session.get("team")
        if isinstance(team, dict) and team.get("id"):
            return team

    # Fallbacks for possible future Rinus response variants.
    team = page_props.get("team")
    if isinstance(team, dict):
        return team

    return {}


def _extract_calendar(text: str) -> dict[str, Any]:
    """Extract the calendar payload from the calendar page."""
    page_props = _page_props(text)

    # Current Rinus structure: pageProps.season + pageProps.items.
    if isinstance(page_props.get("items"), list):
        return {
            "season": page_props.get("season") or {},
            "today": page_props.get("today") or {},
            "items": page_props.get("items") or [],
        }

    # Compatibility with a possible nested calendar payload.
    calendar = page_props.get("calendar")
    if isinstance(calendar, dict):
        return calendar

    return {}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _date_key(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _event_list(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize calendar item's event value to a list of dictionaries."""
    event = item.get("event")
    if isinstance(event, dict):
        return [event]
    if isinstance(event, list):
        return [entry for entry in event if isinstance(entry, dict)]
    return []


def _flatten_matches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    for item in items:
        if not item.get("isMatchDay"):
            continue

        events = _event_list(item)
        for event in events:
            # Match events in the current Rinus payload have id=0, so the ID
            # must NOT be used as a truth test.
            if not any(
                event.get(key)
                for key in ("matchDay", "matchTime", "matchType", "opponent", "teamName")
            ):
                continue

            match = dict(event)
            match["calendar_id"] = item.get("id")
            match["date"] = item.get("date")
            match["day"] = item.get("day")
            match["time"] = event.get("matchTime") or item.get("time")
            match["calendar_type"] = item.get("type")
            matches.append(match)

    return matches


class RinusClient:
    def __init__(self, hass, data: dict[str, Any]):
        self.hass = hass
        self.cookie = (
            data.get(CONF_COOKIE)
            or data.get("cookies")
            or data.get("session_cookie")
            or data.get("auth_cookie")
            or data.get("session")
            or ""
        )
        self._session: ClientSession | None = None

    async def _get(self, path: str) -> str:
        if not self._session:
            self._session = ClientSession(
                timeout=ClientTimeout(total=30),
                headers={
                    "User-Agent": "Home Assistant KNVB Rinus Integration/0.2.1",
                    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    "Referer": BASE_URL + "/nl/",
                },
            )

        headers = {}
        if self.cookie:
            headers["Cookie"] = self.cookie

        async with self._session.get(
            BASE_URL + path,
            headers=headers,
            allow_redirects=True,
        ) as response:
            text = await response.text()
            final_path = str(getattr(response.url, "path", ""))

            if (
                response.status in (401, 403)
                or "/login" in final_path
                or ("loginWall" in text and "Inloggen" in text)
            ):
                raise RinusDataError("De Rinus-sessie/cookie is verlopen of ongeldig.")

            if response.status >= 400:
                raise RinusDataError(
                    f"Rinus gaf HTTP {response.status} terug voor {path}."
                )

            return text

    async def _get_first(self, paths: tuple[str, ...]) -> str:
        last_error: Exception | None = None
        for path in paths:
            try:
                return await self._get(path)
            except Exception as err:  # noqa: BLE001
                last_error = err
        raise RinusDataError(
            str(last_error) if last_error else "Rinus is niet bereikbaar"
        )

    async def async_fetch_all(self) -> dict[str, Any]:
        team_html, calendar_html = await asyncio.gather(
            self._get_first(TEAM_PATHS),
            self._get_first(CALENDAR_PATHS),
        )

        team = _extract_team(team_html)
        calendar = _extract_calendar(calendar_html)

        if not team and not calendar.get("items"):
            raise RinusDataError(
                "Geen Rinus team- of kalendergegevens gevonden. "
                "Controleer de sessie-cookie."
            )

        schedule = team.get("schedule") or {}
        items = calendar.get("items") or []
        matches = _flatten_matches(items)
        today = date.today()

        future_matches = [
            match
            for match in matches
            if (_date_key(match.get("date")) or date.max) >= today
        ]
        future_matches.sort(
            key=lambda match: (
                match.get("date") or "9999-99-99",
                match.get("time") or match.get("matchTime") or "99:99",
            )
        )
        next_match = future_matches[0] if future_matches else None

        future_training_days = [
            item
            for item in items
            if item.get("isTrainingDay")
            and not item.get("isMatchDay")
            and (_date_key(item.get("date")) or date.max) >= today
        ]
        future_training_days.sort(key=lambda item: item.get("date") or "9999-99-99")
        next_training = self._build_next_training(future_training_days, schedule)

        players: dict[str, dict[str, Any]] = {}
        for match in matches:
            for player in match.get("players") or []:
                uuid = player.get("uuid") or player.get("id")
                name = player.get("name") or "Onbekend"
                if not uuid:
                    continue

                entry = players.setdefault(
                    uuid,
                    {
                        "uuid": uuid,
                        "name": name,
                        "total_playing_time": 0,
                        "matches": [],
                    },
                )

                minutes = player.get("playingTime")
                try:
                    minutes = int(minutes or 0)
                except (TypeError, ValueError):
                    minutes = 0

                entry["total_playing_time"] += minutes
                entry["matches"].append(
                    {
                        "match_date": match.get("date"),
                        "match_time": match.get("time"),
                        "opponent": match.get("opponent"),
                        "playing_time": minutes,
                        "match_status": match.get("matchStatus"),
                        "match_type": match.get("matchType"),
                    }
                )

        return {
            "team": team,
            "calendar": calendar,
            "items": items,
            "matches": matches,
            "next_match": next_match,
            "next_training": next_training,
            "players": list(players.values()),
            "fetched_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _build_next_training(
        items: list[dict[str, Any]],
        schedule: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not items:
            return None

        item = items[0]
        weekday = str(item.get("day") or "").lower()
        prefix = {
            "monday": "monday",
            "tuesday": "tuesday",
            "wednesday": "wednesday",
            "thursday": "thursday",
            "friday": "friday",
            "saturday": "saturday",
            "sunday": "sunday",
        }.get(weekday)

        if not prefix:
            return {
                "date": item.get("date"),
                "day": item.get("day"),
            }

        duration = schedule.get(f"{prefix}TrainingDurationTime")
        field_size = schedule.get(f"{prefix}FieldSize")

        return {
            "date": item.get("date"),
            "day": item.get("day"),
            "time": schedule.get(f"{prefix}TrainingTime"),
            "duration": (
                duration.get("title")
                if isinstance(duration, dict)
                else duration
            ),
            "field_size": (
                field_size.get("label")
                if isinstance(field_size, dict)
                else field_size
            ),
        }

    async def async_close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
