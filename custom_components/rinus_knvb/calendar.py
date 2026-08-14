"""Calendar entity for KNVB Rinus."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import RinusCoordinator


class RinusCalendar(CoordinatorEntity[RinusCoordinator], CalendarEntity):
    """Expose Rinus matches and training events as a Home Assistant calendar."""

    _attr_has_entity_name = True
    _attr_name = "Kalender"

    def __init__(self, coordinator: RinusCoordinator) -> None:
        super().__init__(coordinator)
        team = coordinator.data.get("team", {})
        team_name = team.get("teamName") or "Rinus team"
        team_id = team.get("id") or team.get("teamId") or "active"
        self._attr_unique_id = f"{DOMAIN}_calendar"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(team_id))},
            name=team_name,
            manufacturer=MANUFACTURER,
            model="Rinus team",
            configuration_url="https://rinus.knvb.nl/nl/calendar",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event cached by Home Assistant calendar UI."""
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return Rinus events in the requested range."""
        events: list[CalendarEvent] = []
        for item in self.coordinator.data.get("events", []):
            if item.get("type") == "match":
                start_raw = item.get("matchDay")
                if not start_raw:
                    continue
                try:
                    start = datetime.fromisoformat(start_raw).astimezone()
                except ValueError:
                    continue
                end = start + timedelta(minutes=80)
                title = f"Wedstrijd: {item.get('opponent') or 'onbekend'}"
                description = (
                    f"{item.get('matchType', 'wedstrijd')} • "
                    f"{'uit' if item.get('matchAway') else 'thuis'}\n"
                    f"Formatie: {item.get('formation') or 'onbekend'}"
                )
            elif item.get("type") == "training":
                date_raw = item.get("date")
                if not date_raw:
                    continue
                time_raw = item.get("time") or "00:00"
                try:
                    start = datetime.fromisoformat(f"{date_raw}T{time_raw}").astimezone()
                except ValueError:
                    continue
                end = start + timedelta(minutes=90)
                title = "Training"
                description = "Training uit KNVB Rinus"
            else:
                continue

            if start < start_date or start > end_date:
                continue
            events.append(
                CalendarEvent(
                    summary=title,
                    start=start,
                    end=end,
                    description=f"{description}\n\n{ATTRIBUTION}",
                )
            )
        return events
