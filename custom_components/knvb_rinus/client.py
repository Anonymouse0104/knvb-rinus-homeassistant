from __future__ import annotations

import asyncio
import html
import json
import logging
from datetime import date, datetime
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import BASE_URL, CALENDAR_PATHS, CONF_COOKIE, TEAM_PATHS

_LOGGER = logging.getLogger(__name__)


class RinusDataError(Exception):
    pass


def _extract_json_object(text: str, key: str) -> dict[str, Any] | None:
    """Extract a JSON object following a named key from HTML/RSC responses."""
    text = html.unescape(text)
    needles = [f'"{key}"', f'\\"{key}\\"']
    candidates: list[dict[str, Any]] = []
    for needle in needles:
        start = 0
        while True:
            idx = text.find(needle, start)
            if idx < 0:
                break
            colon = text.find(":", idx + len(needle))
            if colon < 0:
                break
            pos = colon + 1
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos >= len(text) or text[pos] != "{":
                start = idx + len(needle)
                continue
            try:
                obj, _ = json.JSONDecoder().raw_decode(text[pos:])
                if isinstance(obj, dict):
                    candidates.append(obj)
            except json.JSONDecodeError:
                pass
            start = idx + len(needle)
    if not candidates:
        return None
    # Prefer the real team object over navigation/UI objects also named "team".
    return max(
        candidates,
        key=lambda obj: (
            100 if obj.get("teamName") else 0,
            50 if isinstance(obj.get("schedule"), dict) else 0,
            20 if obj.get("seasonTitle") else 0,
            len(obj),
        ),
    )


def _extract_json_array(text: str, key: str) -> list[Any] | None:
    text = html.unescape(text)
    needles = [f'"{key}"', f'\\"{key}\\"']
    for needle in needles:
        start = 0
        while True:
            idx = text.find(needle, start)
            if idx < 0:
                break
            colon = text.find(":", idx + len(needle))
            if colon < 0:
                break
            pos = colon + 1
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos >= len(text) or text[pos] != "[":
                start = idx + len(needle)
                continue
            try:
                obj, _ = json.JSONDecoder().raw_decode(text[pos:])
                if isinstance(obj, list):
                    return obj
            except json.JSONDecodeError:
                pass
            start = idx + len(needle)
    return None


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
    except ValueError:
        return None


def _parse_time(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) >= 5 and text[2] == ":":
        return text[:5]
    return None


def _flatten_matches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in items:
        event = item.get("event")
        if item.get("isMatchDay") and isinstance(event, dict) and event.get("id"):
            match = dict(event)
            match["date"] = item.get("date")
            match["day"] = item.get("day")
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
                    "User-Agent": "Home Assistant KNVB Rinus Integration/0.2.0",
                    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    "Referer": BASE_URL + "/nl/",
                },
            )
        headers = {}
        if self.cookie:
            headers["Cookie"] = self.cookie
        async with self._session.get(BASE_URL + path, headers=headers, allow_redirects=True) as response:
            text = await response.text()
            final_path = str(getattr(response.url, "path", ""))
            if response.status in (401, 403) or "/login" in final_path or ("loginWall" in text and "Inloggen" in text):
                raise RinusDataError("De Rinus-sessie/cookie is verlopen of ongeldig.")
            if response.status >= 400:
                raise RinusDataError(f"Rinus gaf HTTP {response.status} terug voor {path}.")
            return text

    async def _get_first(self, paths: tuple[str, ...]) -> str:
        last_error = None
        for path in paths:
            try:
                return await self._get(path)
            except Exception as err:
                last_error = err
        raise RinusDataError(str(last_error) if last_error else "Rinus is niet bereikbaar")

    async def async_fetch_all(self) -> dict[str, Any]:
        team_html, calendar_html = await asyncio.gather(
            self._get_first(TEAM_PATHS),
            self._get_first(CALENDAR_PATHS),
        )

        team = _extract_json_object(team_html, "team") or {}
        calendar = _extract_json_object(calendar_html, "calendar") or {}
        if not calendar:
            # On some Rinus responses season/items live directly in the page payload.
            items = _extract_json_array(calendar_html, "items") or []
            season = _extract_json_object(calendar_html, "season") or {}
            calendar = {"items": items, "season": season}

        if not team and not calendar.get("items"):
            raise RinusDataError("Geen Rinus team- of kalendergegevens gevonden. Controleer de sessie-cookie.")

        schedule = team.get("schedule") or {}
        items = calendar.get("items") or []
        matches = _flatten_matches(items)
        today = date.today()

        future_matches = [m for m in matches if (_date_key(m.get("date")) or date.max) >= today]
        future_matches.sort(key=lambda m: (m.get("date") or "9999-99-99", m.get("time") or "99:99"))

        next_match = future_matches[0] if future_matches else None
        future_training_days = [
            item for item in items
            if item.get("isTrainingDay") and not item.get("isMatchDay") and (_date_key(item.get("date")) or date.max) >= today
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
                entry = players.setdefault(uuid, {"uuid": uuid, "name": name, "total_playing_time": 0, "matches": []})
                minutes = player.get("playingTime")
                try:
                    minutes = int(minutes or 0)
                except (TypeError, ValueError):
                    minutes = 0
                entry["total_playing_time"] += minutes
                entry["matches"].append({
                    "match_id": match.get("id"),
                    "date": match.get("date"),
                    "playing_time": minutes,
                    "match_status": match.get("matchStatus"),
                })

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
    def _build_next_training(items: list[dict[str, Any]], schedule: dict[str, Any]) -> dict[str, Any] | None:
        if not items:
            return None
        item = items[0]
        weekday = str(item.get("day") or "").lower()
        mapping = {
            "monday": "monday",
            "tuesday": "tuesday",
            "wednesday": "wednesday",
            "thursday": "thursday",
            "friday": "friday",
            "saturday": "saturday",
            "sunday": "sunday",
        }
        prefix = mapping.get(weekday)
        if not prefix:
            return {"date": item.get("date"), "day": item.get("day")}
        return {
            "date": item.get("date"),
            "day": item.get("day"),
            "time": schedule.get(f"{prefix}TrainingTime"),
            "duration": (schedule.get(f"{prefix}TrainingDurationTime") or {}).get("title") if isinstance(schedule.get(f"{prefix}TrainingDurationTime"), dict) else schedule.get(f"{prefix}TrainingDurationTime"),
            "field_size": (schedule.get(f"{prefix}FieldSize") or {}).get("label") if isinstance(schedule.get(f"{prefix}FieldSize"), dict) else schedule.get(f"{prefix}FieldSize"),
        }
