from __future__ import annotations

import asyncio
import html
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import BASE_URL, CALENDAR_PATHS, CONF_COOKIE, PLAYER_PATH, TEAM_PATHS

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
    """Return page props from either HTML __NEXT_DATA__ or a raw JSON response."""
    payload = _extract_next_data(text)

    # Some Rinus routes (notably /profile/team) have also returned the data
    # object directly as JSON instead of wrapping it in __NEXT_DATA__.
    if payload is None:
        try:
            raw_payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            raw_payload = None
        if isinstance(raw_payload, dict):
            payload = raw_payload

    if not isinstance(payload, dict):
        return {}

    props = payload.get("props")
    if isinstance(props, dict):
        page_props = props.get("pageProps")
        if isinstance(page_props, dict):
            return page_props

    # Raw JSON response: the response itself is the page payload.
    return payload


def _walk_dicts(value: Any):
    """Yield all dictionaries in a nested Rinus payload."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _looks_like_team(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value.get("teamName"))
        and ("schedule" in value or "clubName" in value or "teamAgeLabel" in value)
    )


def _extract_team(text: str) -> dict[str, Any]:
    """Extract the active team from the profile/team page payload.

    Rinus has changed the exact nesting of the profile response more than once.
    The current page exposes a `team` object in pageProps; older variants may
    place it below session or another wrapper. We therefore search the payload
    for the first dictionary that has the characteristic team fields.
    """
    page_props = _page_props(text)

    # Known current structure from the observed Rinus response.
    for candidate in (
        page_props.get("team"),
        (page_props.get("session") or {}).get("team")
        if isinstance(page_props.get("session"), dict)
        else None,
        page_props.get("activeTeam"),
        page_props.get("activeteam"),
    ):
        if _looks_like_team(candidate):
            return candidate

    # Robust fallback: find a nested object with the team signature.
    for candidate in _walk_dicts(page_props):
        if _looks_like_team(candidate):
            return candidate

    return {}


def _extract_roster(text: str) -> list[dict[str, Any]]:
    """Extract the complete current team roster from the Rinus profile payload.

    Rinus can expose player lists in more than one place (the active team
    object, nested team objects, and match payloads). We merge all valid
    player records and de-duplicate by UUID so a newly added team member is
    not missed simply because the payload nesting changed.
    """
    page_props = _page_props(text)
    candidates: list[list[dict[str, Any]]] = []

    def normalize_players(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for player in value:
            if not isinstance(player, dict):
                continue
            uuid = (
                player.get("uuid")
                or player.get("uUid")
                or player.get("uid")
                or player.get("id")
                or player.get("playerId")
                or player.get("userId")
                or player.get("user_id")
            )
            name = (
                player.get("name")
                or player.get("playerName")
                or player.get("displayName")
                or player.get("fullName")
            )
            if uuid and name:
                result.append({
                    "uuid": str(uuid),
                    "name": str(name),
                    "raw_player": player,
                })
        return result

    # The observed current structure has pageProps.team as a list.
    team_list = page_props.get("team")
    if isinstance(team_list, list):
        for team_entry in team_list:
            if isinstance(team_entry, dict):
                players = normalize_players(team_entry.get("players"))
                if players:
                    candidates.append(players)

    # Also inspect every nested dictionary. This makes the parser resilient
    # to Rinus moving the roster or returning it in a different wrapper.
    for candidate in _walk_dicts(page_props):
        players = normalize_players(candidate.get("players"))
        if players:
            candidates.append(players)

    # Merge all candidates. Prefer the most complete record when the same UUID
    # occurs in multiple payload sections.
    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        for player in candidate:
            key = player["uuid"]
            existing = unique.get(key)
            if existing is None or len(player.get("raw_player", {})) > len(existing.get("raw_player", {})):
                unique[key] = player

    roster = [
        {
            "uuid": player["uuid"],
            "name": player["name"],
            "raw_player": player.get("raw_player", {}),
        }
        for player in unique.values()
    ]
    _LOGGER.debug(
        "Rinus roster parser found %d unique players in %d candidate lists",
        len(roster),
        len(candidates),
    )
    return roster



def _extract_player_modal_roster(text: str) -> list[dict[str, Any]]:
    """Extract the complete editable player list from the Rinus players modal.

    The browser uses /api/modals/edit/players/open to populate the player
    editor.  Its JSON response contains a form/orderlist with entries named
    team_playerItem_text_N.  This endpoint is authoritative for the complete
    manually maintained team roster, including newly added players that are
    not present in the profile/team response.
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        _LOGGER.debug("Rinus spelersmodal gaf geen geldige JSON-response")
        return []

    roster: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for candidate in walk(payload):
        items = candidate.get("items")
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            options = item.get("options")
            if not isinstance(options, list):
                continue

            for option in options:
                if not isinstance(option, dict):
                    continue
                input_data = option.get("input")
                if not isinstance(input_data, dict):
                    continue
                input_name = str(input_data.get("name") or "")
                if not input_name.startswith("team_playerItem_text_"):
                    continue

                name = str(input_data.get("value") or "").strip()
                if not name:
                    # Rinus always includes an extra empty row for adding the
                    # next player. It is not part of the roster.
                    continue

                option_id = str(option.get("id") or "")
                parts = option_id.split("::")
                uuid = parts[1].strip() if len(parts) >= 2 and parts[1].strip() else ""
                index = input_name.rsplit("_", 1)[-1]

                # A populated Rinus player normally has a UUID.  Keep a stable
                # fallback for older/manual entries that do not have one.
                player_id = uuid or f"name:{name.casefold()}"
                if player_id in seen:
                    continue
                seen.add(player_id)

                roster.append(
                    {
                        "uuid": player_id,
                        "name": name,
                        "index": index,
                        "raw_player": option,
                        "source": "Rinus /api/modals/edit/players/open",
                    }
                )

    _LOGGER.debug(
        "Rinus players modal parser found %d roster entries", len(roster)
    )
    return roster

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

    calendar = page_props.get("calendar")
    if isinstance(calendar, dict):
        return calendar

    # Compatibility fallback for a nested wrapper.
    for candidate in _walk_dicts(page_props):
        if isinstance(candidate.get("items"), list) and (
            "season" in candidate or "today" in candidate
        ):
            return candidate

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
        events = _event_list(item)
        if not events and isinstance(item.get("match"), dict):
            events = [item["match"]]

        for event in events:
            if not item.get("isMatchDay") and not any(
                event.get(key)
                for key in ("matchDay", "matchTime", "matchType", "opponent", "teamName")
            ):
                continue

            match = dict(event)
            match["calendar_id"] = item.get("id")
            match["date"] = item.get("date") or str(event.get("matchDay", ""))[:10]
            match["day"] = item.get("day")
            match["time"] = event.get("matchTime") or item.get("time")
            match["calendar_type"] = item.get("type")
            matches.append(match)

    return matches


def _weekday_name(value: date) -> str:
    return (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )[value.weekday()]


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
        ).strip()
        # The config flow asks for the CraftSessionId value only.  Rinus expects
        # a normal HTTP Cookie header, so turn a bare session value into the
        # actual cookie pair.  Also accept a full Cookie header for backwards
        # compatibility.
        if self.cookie and "=" not in self.cookie:
            self.cookie = f"CraftSessionId={self.cookie}"
        self._session: ClientSession | None = None

    async def _get(self, path: str) -> str:
        if not self._session:
            self._session = ClientSession(
                timeout=ClientTimeout(total=30),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
                    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                },
            )

        headers = {
            # Rinus opens the player editor from the team profile page.
            # Keep the same browser-style referer for this modal endpoint.
            "Referer": BASE_URL + ("/profile/team" if path == PLAYER_PATH else path),
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        async with self._session.get(
            BASE_URL + path,
            headers=headers,
            allow_redirects=True,
        ) as response:
            text = await response.text()
            final_path = str(getattr(response.url, "path", ""))
            _LOGGER.debug(
                "Rinus GET %s -> %s (%s), final path=%s, %d bytes",
                path,
                response.status,
                response.headers.get("Content-Type", ""),
                final_path,
                len(text),
            )

            if response.status in (401, 403) or "/login" in final_path:
                raise RinusDataError("De Rinus-sessie/cookie is verlopen of ongeldig.")

            if response.status >= 400:
                raise RinusDataError(f"Rinus gaf HTTP {response.status} terug voor {path}.")

            return text

    async def _get_first(self, paths: tuple[str, ...]) -> str:
        last_error: Exception | None = None
        for path in paths:
            try:
                return await self._get(path)
            except Exception as err:  # noqa: BLE001
                last_error = err
        raise RinusDataError(str(last_error) if last_error else "Rinus is niet bereikbaar")

    async def async_fetch_all(self) -> dict[str, Any]:
        # The authenticated team data is served by the Rinus modal API.
        # This is the endpoint used by the browser on /profile/team and it
        # returns the team/schedule object directly as JSON.
        team_html, calendar_html, players_html = await asyncio.gather(
            self._get_first(TEAM_PATHS),
            self._get_first(CALENDAR_PATHS),
            self._get(PLAYER_PATH),
        )

        team = _extract_team(team_html)
        # The editable players modal is the authoritative roster source.
        # /api/modals/get/team/profile does not contain manually added players
        # such as newly created entries in the Rinus team editor.
        roster = _extract_player_modal_roster(players_html)
        calendar = _extract_calendar(calendar_html)
        _LOGGER.debug(
            "Rinus parsed team=%s, roster_players=%d, calendar_items=%d",
            bool(team),
            len(roster),
            len(calendar.get("items") or []),
        )

        if not team:
            _LOGGER.warning(
                "Rinus teamgegevens konden niet uit de profielresponses worden gehaald"
            )
        if not roster:
            _LOGGER.warning(
                "Rinus spelersmodal bevat geen bruikbare spelerslijst"
            )
        if not calendar.get("items"):
            _LOGGER.warning("Rinus kalender bevat geen items")

        if not team and not calendar.get("items"):
            raise RinusDataError(
                "Geen Rinus team- of kalendergegevens gevonden. Controleer de sessie-cookie."
            )

        schedule = team.get("schedule") or {}
        items = calendar.get("items") or []
        matches = _flatten_matches(items)
        today = date.today()

        def match_datetime(match: dict[str, Any]) -> datetime:
            parsed = _parse_dt(match.get("matchDay"))
            if parsed:
                return parsed
            day = _date_key(match.get("date")) or date.max
            try:
                hour, minute = (match.get("time") or "23:59").split(":")[:2]
                return datetime.combine(day, datetime.min.time()).replace(
                    hour=int(hour), minute=int(minute)
                )
            except (ValueError, TypeError):
                return datetime.combine(day, datetime.max.time())

        future_matches = [m for m in matches if match_datetime(m).date() >= today]
        future_matches.sort(key=match_datetime)
        next_match = future_matches[0] if future_matches else None

        # Prefer the actual team schedule. Fall back to calendar training flags.
        future_training_days: list[dict[str, Any]] = []
        for item in items:
            item_date = _date_key(item.get("date"))
            if not item_date or item_date < today or item.get("isMatchDay"):
                continue
            if item.get("isTrainingDay"):
                future_training_days.append(item)

        if not future_training_days and schedule:
            for offset in range(0, 15):
                candidate_date = today + timedelta(days=offset)
                weekday = _weekday_name(candidate_date)
                if schedule.get(f"{weekday}ActiveTrainingDay"):
                    future_training_days.append(
                        {"date": candidate_date.isoformat(), "day": weekday}
                    )
                    break

        future_training_days.sort(key=lambda item: item.get("date") or "9999-99-99")
        next_training = self._build_next_training(future_training_days, schedule)

        # Start with the complete Rinus team roster so players who have not
        # appeared in a match yet are still exposed with 0 minutes.
        players: dict[str, dict[str, Any]] = {}
        for roster_player in roster:
            uuid = str(roster_player["uuid"])
            players[uuid] = {
                "uuid": roster_player["uuid"],
                "name": roster_player["name"],
                "total_playing_time": 0,
                "matches": [],
                "raw_player": roster_player.get("raw_player", roster_player),
                "roster_index": roster_player.get("index"),
                "source": roster_player.get("source", "Rinus /api/modals/edit/players/open"),
            }

        # Merge match participation and playing time into the roster.
        for match in matches:
            for player in match.get("players") or []:
                uuid = player.get("uuid") or player.get("id") or player.get("uUid")
                name = player.get("name") or player.get("playerName") or "Onbekend"
                if not uuid:
                    continue

                uuid = str(uuid)
                entry = players.setdefault(
                    uuid,
                    {
                        "uuid": uuid,
                        "name": name,
                        "total_playing_time": 0,
                        "matches": [],
                        "raw_player": player,
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
            "roster": roster,
            "fetched_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _build_next_training(items: list[dict[str, Any]], schedule: dict[str, Any]) -> dict[str, Any] | None:
        if not items:
            return None

        item = items[0]
        item_date = _date_key(item.get("date"))
        if not item_date:
            return {"date": item.get("date"), "day": item.get("day")}

        prefix = _weekday_name(item_date)
        duration = schedule.get(f"{prefix}TrainingDurationTime")
        field_size = schedule.get(f"{prefix}FieldSize")

        return {
            "date": item_date.isoformat(),
            "day": prefix,
            "time": schedule.get(f"{prefix}TrainingTime"),
            "duration": duration.get("title") if isinstance(duration, dict) else duration,
            "field_size": field_size.get("label") if isinstance(field_size, dict) else field_size,
        }

    async def async_close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
