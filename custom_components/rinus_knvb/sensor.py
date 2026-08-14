"""Sensors for KNVB Rinus."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, NAME
from .coordinator import RinusCoordinator


def _device(team: dict[str, Any]) -> DeviceInfo:
    team_name = team.get("teamName") or team.get("shortTeamName") or "Rinus team"
    team_id = team.get("id") or team.get("teamId") or "active"
    return DeviceInfo(
        identifiers={(DOMAIN, str(team_id))},
        name=team_name,
        manufacturer=MANUFACTURER,
        model="Rinus team",
        configuration_url="https://rinus.knvb.nl/nl/calendar",
    )


def _match_attrs(match: dict[str, Any] | None) -> dict[str, Any]:
    if not match:
        return {}
    attrs = {
        "match_id": match.get("id"),
        "opponent": match.get("opponent"),
        "match_day": match.get("matchDay"),
        "match_time": match.get("matchTime"),
        "match_type": match.get("matchType"),
        "home_or_away": "uit" if match.get("matchAway") else "thuis",
        "formation": match.get("formation"),
        "match_status": match.get("matchStatus"),
        "score": match.get("matchScore"),
        "players": match.get("players", []),
        "current_lineup": match.get("currentLineUp", []),
        ATTR_ATTRIBUTION: ATTRIBUTION,
    }
    return attrs


class RinusSensor(CoordinatorEntity[RinusCoordinator], SensorEntity):
    """Base Rinus sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RinusCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_device_info = _device(coordinator.data.get("team", {}))


class RinusSeasonSensor(RinusSensor):
    """Current season."""

    def __init__(self, coordinator: RinusCoordinator) -> None:
        super().__init__(coordinator, "season", "Seizoen")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("season", {}).get("title")


class RinusNextMatchSensor(RinusSensor):
    """Next match sensor."""

    def __init__(self, coordinator: RinusCoordinator) -> None:
        super().__init__(coordinator, "next_match", "Volgende wedstrijd")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        value = (self.coordinator.data.get("next_match") or {}).get("matchDay")
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).astimezone()
        except ValueError:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _match_attrs(self.coordinator.data.get("next_match"))


class RinusNextOpponentSensor(RinusSensor):
    """Next opponent."""

    def __init__(self, coordinator: RinusCoordinator) -> None:
        super().__init__(coordinator, "next_opponent", "Volgende tegenstander")

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data.get("next_match") or {}).get("opponent")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _match_attrs(self.coordinator.data.get("next_match"))


class RinusNextTrainingSensor(RinusSensor):
    """Next scheduled training."""

    def __init__(self, coordinator: RinusCoordinator) -> None:
        super().__init__(coordinator, "next_training", "Volgende training")

    @property
    def native_value(self) -> str | None:
        training = self.coordinator.data.get("next_training") or {}
        if not training:
            return None
        return f"{training.get('date')} {training.get('time') or ''}".strip()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "date": (self.coordinator.data.get("next_training") or {}).get("date"),
            "time": (self.coordinator.data.get("next_training") or {}).get("time"),
        }


class RinusTeamSensor(RinusSensor):
    """Team information sensor with the complete team data as attributes."""

    def __init__(self, coordinator: RinusCoordinator) -> None:
        super().__init__(coordinator, "team", "Team")

    @property
    def native_value(self) -> str | None:
        team = self.coordinator.data.get("team", {})
        return team.get("teamName") or team.get("title")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        team = dict(self.coordinator.data.get("team", {}))
        team[ATTR_ATTRIBUTION] = ATTRIBUTION
        return team


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up sensors."""
    coordinator: RinusCoordinator = entry.runtime_data
    async_add_entities(
        [
            RinusSeasonSensor(coordinator),
            RinusNextMatchSensor(coordinator),
            RinusNextOpponentSensor(coordinator),
            RinusNextTrainingSensor(coordinator),
            RinusTeamSensor(coordinator),
        ]
    )
