from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION


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

    entities = [
        RinusSensor(coordinator, entry, device_info, "season", "Seizoen", "mdi:calendar-range"),
        RinusSensor(coordinator, entry, device_info, "team", "Team", "mdi:soccer-field"),
        RinusSensor(coordinator, entry, device_info, "next_opponent", "Volgende tegenstander", "mdi:shield-account"),
        RinusSensor(coordinator, entry, device_info, "next_training", "Volgende training", "mdi:whistle"),
        RinusSensor(coordinator, entry, device_info, "next_match", "Volgende wedstrijd", "mdi:soccer"),
        RinusSensor(coordinator, entry, device_info, "matches", "Wedstrijden", "mdi:calendar-multiple"),
        RinusSensor(coordinator, entry, device_info, "players", "Spelers", "mdi:account-group"),
    ]
    async_add_entities(entities)


class RinusSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, device_info, kind: str, name: str, icon: str):
        super().__init__(coordinator)
        self._entry = entry
        self._kind = kind
        self._attr_name = name
        self._attr_icon = icon
        self._attr_has_entity_name = True
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_{kind}"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._kind == "season":
            return (data.get("team") or {}).get("seasonTitle") or (data.get("calendar") or {}).get("season", {}).get("title") or "Onbekend"
        if self._kind == "team":
            return (data.get("team") or {}).get("teamName") or (data.get("team") or {}).get("title") or "Onbekend"
        if self._kind == "next_opponent":
            match = data.get("next_match") or {}
            return self._opponent(match) or "Onbekend"
        if self._kind == "next_training":
            training = data.get("next_training") or {}
            if not training:
                return "Onbekend"
            return training.get("time") or "Gepland"
        if self._kind == "next_match":
            match = data.get("next_match") or {}
            if not match:
                return "Geen wedstrijd"
            return match.get("date") or "Gepland"
        if self._kind == "matches":
            return len(data.get("matches") or [])
        if self._kind == "players":
            return len(data.get("players") or [])
        return "Onbekend"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        team = data.get("team") or {}
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
            }
        if self._kind == "next_opponent":
            match = data.get("next_match") or {}
            return self._match_attrs(match)
        if self._kind == "next_training":
            return data.get("next_training") or {}
        if self._kind == "next_match":
            return self._match_attrs(data.get("next_match") or {})
        if self._kind == "matches":
            return {"matches": [self._match_summary(m) for m in data.get("matches") or []]}
        if self._kind == "players":
            return {"players": data.get("players") or []}
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
        attrs["current_lineup"] = match.get("currentLineUp") or []
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
            "players": match.get("players") or [],
        }
