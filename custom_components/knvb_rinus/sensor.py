from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="KNVB Rinus",
        manufacturer="KNVB",
        model="Rinus",
        sw_version=VERSION,
        configuration_url="https://rinus.knvb.nl/",
    )

    static_entities: list[SensorEntity] = [
        RinusSensor(coordinator, entry, device_info, "connection", "Verbinding", "mdi:cloud-check"),
        RinusSensor(coordinator, entry, device_info, "season", "Seizoen", "mdi:calendar-range"),
        RinusSensor(coordinator, entry, device_info, "team", "Team", "mdi:soccer-field"),
        RinusSensor(coordinator, entry, device_info, "next_opponent", "Volgende tegenstander", "mdi:shield-account"),
        RinusSensor(coordinator, entry, device_info, "next_training", "Volgende training", "mdi:whistle"),
        RinusSensor(coordinator, entry, device_info, "next_match", "Volgende wedstrijd", "mdi:soccer"),
        RinusSensor(coordinator, entry, device_info, "matches", "Wedstrijden", "mdi:calendar-multiple"),
        RinusSensor(coordinator, entry, device_info, "players", "Spelers", "mdi:account-group"),
    ]

    player_entities: dict[str, RinusPlayerSensor] = {}
    match_entities: dict[str, RinusMatchSensor] = {}
    dynamic_added = False

    def player_key(player: dict[str, Any]) -> str:
        return str(player.get("uuid") or player.get("id") or player.get("name") or "unknown")

    def match_key(match: dict[str, Any], index: int = 0) -> str:
        return str(match.get("id") or match.get("calendar_id") or f"{index}_{match.get('date')}_{match.get('time')}")

    def sync_dynamic_entities() -> None:
        nonlocal dynamic_added
        current_players = coordinator.data.get("players", []) or []
        current_keys = {player_key(player) for player in current_players}
        new_entities: list[SensorEntity] = []

        for player in current_players:
            key = player_key(player)
            if key in player_entities:
                # Keep the entity object; its state/attributes are read from coordinator data.
                continue
            entity = RinusPlayerSensor(
                coordinator, entry, device_info, key, str(player.get("name") or "Onbekende speler")
            )
            player_entities[key] = entity
            new_entities.append(entity)

        for key in list(player_entities):
            if key in current_keys:
                continue
            entity = player_entities.pop(key)
            hass.async_create_task(entity.async_remove(force_remove=True))

        current_matches = coordinator.data.get("matches", []) or []
        current_match_keys = {match_key(match, index) for index, match in enumerate(current_matches)}

        for index, match in enumerate(current_matches):
            key = match_key(match, index)
            if key in match_entities:
                continue
            entity = RinusMatchSensor(coordinator, entry, device_info, key)
            match_entities[key] = entity
            new_entities.append(entity)

        for key in list(match_entities):
            if key in current_match_keys:
                continue
            entity = match_entities.pop(key)
            hass.async_create_task(entity.async_remove(force_remove=True))

        if new_entities:
            async_add_entities(new_entities)
            dynamic_added = True

    # Add static entities first, then build the initial dynamic set.
    async_add_entities(static_entities)
    sync_dynamic_entities()

    remove_listener = coordinator.async_add_listener(sync_dynamic_entities)
    entry.async_on_unload(remove_listener)


class RinusBaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, device_info):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = device_info


class RinusSensor(RinusBaseSensor):
    def __init__(self, coordinator, entry, device_info, kind: str, name: str, icon: str):
        super().__init__(coordinator, entry, device_info)
        self._kind = kind
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{kind}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._kind == "connection":
            if self.coordinator.last_update_success:
                return "Verbonden"
            return "Cookie verlopen of Rinus niet bereikbaar"
        if self._kind == "season":
            return (data.get("team") or {}).get("seasonTitle") or (data.get("calendar") or {}).get("season", {}).get("title") or "Onbekend"
        if self._kind == "team":
            return (data.get("team") or {}).get("teamName") or (data.get("team") or {}).get("title") or "Onbekend"
        if self._kind == "next_opponent":
            return self._opponent(data.get("next_match") or {}) or "Onbekend"
        if self._kind == "next_training":
            training = data.get("next_training") or {}
            return training.get("time") if training else "Onbekend"
        if self._kind == "next_match":
            match = data.get("next_match") or {}
            if not match:
                return "Geen wedstrijd"
            return f"{match.get('date')} {match.get('time')}".strip()
        if self._kind == "matches":
            return len(data.get("matches") or [])
        if self._kind == "players":
            return len(data.get("players") or [])
        return "Onbekend"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        team = data.get("team") or {}
        if self._kind == "connection":
            return {
                "last_successful_update": self.coordinator.last_update_success,
                "last_update": data.get("fetched_at"),
                "update_interval_seconds": int(self.coordinator.update_interval.total_seconds()),
            }
        if self._kind == "season":
            return {"season_id": team.get("season"), "season_title": team.get("seasonTitle")}
        if self._kind == "team":
            return {
                "team_id": team.get("id"),
                "team_sportlink_id": team.get("teamId"),
                "team_name": team.get("teamName"),
                "short_team_name": team.get("shortTeamName"),
                "club_id": team.get("clubId"),
                "club_name": team.get("clubName"),
                "age": team.get("teamAgeLabel"),
                "age_id": team.get("teamAgeId"),
                "match_duration": team.get("matchDuration"),
                "match_team_size": team.get("matchTeamSize"),
                "is_futsal": team.get("isFutsal"),
                "schedule": team.get("schedule"),
                "raw_team": team,
                "data_source": "Rinus /api/modals/get/team/profile",
            }
        if self._kind == "next_opponent":
            return self._match_attrs(data.get("next_match") or {})
        if self._kind == "next_training":
            return data.get("next_training") or {}
        if self._kind == "next_match":
            return self._match_attrs(data.get("next_match") or {})
        if self._kind == "matches":
            return {
                "matches": [self._match_summary(m) for m in data.get("matches") or []],
                "calendar_items": len(data.get("items") or []),
                "fetched_at": data.get("fetched_at"),
            }
        if self._kind == "players":
            return {
                "players": data.get("players") or [],
                "roster": data.get("roster") or [],
                "fetched_at": data.get("fetched_at"),
            }
        return {}

    @staticmethod
    def _opponent(match: dict[str, Any]) -> str | None:
        for key in ("opponent", "opponentName", "opponent_name", "against", "teamOpponent"):
            if match.get(key):
                return str(match[key])
        for key in ("homeTeam", "awayTeam", "home_team", "away_team"):
            value = match.get(key)
            if isinstance(value, dict) and value.get("name"):
                return value["name"]
        return None

    def _match_attrs(self, match: dict[str, Any]) -> dict[str, Any]:
        if not match:
            return {}
        attrs = dict(match)
        attrs["opponent"] = self._opponent(match)
        attrs["players"] = match.get("players") or []
        attrs["current_lineup"] = match.get("currentLineUp") or match.get("current_lineup") or []
        return attrs

    @staticmethod
    def _match_summary(match: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": match.get("id"),
            "date": match.get("date"),
            "day": match.get("day"),
            "time": match.get("time"),
            "opponent": RinusSensor._opponent(match),
            "formation": match.get("formation"),
            "match_status": match.get("matchStatus"),
            "match_type": match.get("matchType"),
            "players": match.get("players") or [],
            "raw": match,
        }


class RinusPlayerSensor(RinusBaseSensor):
    """One Home Assistant sensor containing the complete known data for a player."""

    def __init__(self, coordinator, entry, device_info, player_id: str, name: str):
        super().__init__(coordinator, entry, device_info)
        self._player_id = player_id
        self._attr_name = name
        self._attr_icon = "mdi:account"
        self._attr_unique_id = f"{entry.entry_id}_player_{player_id}"

    def _player(self) -> dict[str, Any]:
        for player in self.coordinator.data.get("players", []):
            if str(player.get("uuid") or player.get("id") or player.get("name")) == self._player_id:
                return player
        return {}

    @property
    def native_value(self):
        return self._player().get("total_playing_time", 0)

    @property
    def native_unit_of_measurement(self):
        return "min"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        player = self._player()
        attrs = dict(player)
        attrs["match_count"] = len(player.get("matches") or [])
        attrs["raw_player"] = player.get("raw_player")
        attrs["data_source"] = "Rinus team roster + match data"
        return attrs


class RinusMatchSensor(RinusBaseSensor):
    """One Home Assistant sensor per match with all match/player details as attributes."""

    def __init__(self, coordinator, entry, device_info, match_id: str):
        super().__init__(coordinator, entry, device_info)
        self._match_id = match_id
        self._attr_icon = "mdi:soccer-field"
        self._attr_unique_id = f"{entry.entry_id}_match_{match_id}"

    def _match(self) -> dict[str, Any]:
        for index, match in enumerate(self.coordinator.data.get("matches", []) or []):
            candidate = str(match.get("id") or match.get("calendar_id") or f"{index}_{match.get('date')}_{match.get('time')}")
            if candidate == self._match_id:
                return match
        return {}

    @property
    def name(self) -> str:
        match = self._match()
        opponent = RinusSensor._opponent(match) or "Onbekende tegenstander"
        date = match.get("date") or match.get("matchDay") or "Onbekende datum"
        return f"Wedstrijd {date} - {opponent}"

    @property
    def native_value(self):
        match = self._match()
        if not match:
            return "Onbekend"
        for key in ("result", "score", "matchStatus", "status"):
            if match.get(key) is not None:
                return str(match[key])
        return "Gepland"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        match = self._match()
        if not match:
            return {}
        attrs = dict(match)
        attrs["opponent"] = RinusSensor._opponent(match)
        attrs["players"] = match.get("players") or []
        attrs["current_lineup"] = match.get("currentLineUp") or match.get("current_lineup") or []
        return attrs
