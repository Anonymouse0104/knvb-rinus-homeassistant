"""Small client for the authenticated KNVB Rinus web application."""

from __future__ import annotations

import json
import re
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import BASE_URL, CALENDAR_PATH, PROFILE_TEAM_PATH


class RinusError(Exception):
    """Base exception for Rinus errors."""


class RinusAuthError(RinusError):
    """Authentication/session error."""


class RinusConnectionError(RinusError):
    """Connection or parsing error."""


def extract_next_data(html: str) -> dict[str, Any]:
    """Extract the Next.js __NEXT_DATA__ JSON object from a Rinus page."""
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise RinusConnectionError("Rinus page did not contain __NEXT_DATA__")

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as err:
        raise RinusConnectionError("Invalid __NEXT_DATA__ JSON") from err


def page_props(data: dict[str, Any]) -> dict[str, Any]:
    """Return Next.js pageProps."""
    try:
        return data["props"]["pageProps"]
    except (KeyError, TypeError) as err:
        raise RinusConnectionError("Rinus response has no pageProps") from err


def extract_craft_session(cookie_header: str) -> str:
    """Extract only the CraftSessionId from a browser cookie string."""
    for part in cookie_header.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name == "CraftSessionId" and value:
            return value
    # Also accept a raw CraftSessionId value for convenience.
    if cookie_header and ";" not in cookie_header and "=" not in cookie_header:
        return cookie_header.strip()
    raise RinusAuthError("No CraftSessionId was found in the supplied cookie")


class RinusClient:
    """Authenticated client for Rinus pages."""

    def __init__(self, session: ClientSession, session_cookie: str) -> None:
        self._session = session
        self._session_cookie = extract_craft_session(session_cookie)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            "User-Agent": "Home Assistant KNVB Rinus integration",
            "Cookie": f"CraftSessionId={self._session_cookie}",
        }

    async def _get_page(self, path: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                f"{BASE_URL}{path}",
                headers=self.headers,
                allow_redirects=True,
            ) as response:
                if response.status in (401, 403):
                    raise RinusAuthError("Rinus session is no longer valid")
                if response.status != 200:
                    raise RinusConnectionError(
                        f"Rinus returned HTTP {response.status}"
                    )
                html = await response.text()
        except RinusError:
            raise
        except (ClientError, TimeoutError) as err:
            raise RinusConnectionError("Could not connect to Rinus") from err

        data = extract_next_data(html)
        props = page_props(data)
        # A logged-out page can still return HTTP 200. The authenticated calendar
        # contains an items list; its absence is our reliable auth check.
        if path == CALENDAR_PATH and "items" not in props:
            raise RinusAuthError("Rinus session did not return calendar data")
        return props

    async def async_get_calendar(self) -> dict[str, Any]:
        """Fetch the active team's calendar page data."""
        return await self._get_page(CALENDAR_PATH)

    async def async_get_team(self) -> dict[str, Any]:
        """Fetch the active team's profile page data."""
        return await self._get_page(PROFILE_TEAM_PATH)

    async def async_validate(self) -> dict[str, Any]:
        """Validate the session and return calendar page props."""
        return await self.async_get_calendar()
