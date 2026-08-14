"""Constants for the Rinus KNVB integration."""

from datetime import timedelta

DOMAIN = "rinus_knvb"
NAME = "KNVB Rinus"
MANUFACTURER = "KNVB"
BASE_URL = "https://rinus.knvb.nl"
CALENDAR_PATH = "/nl/calendar"
PROFILE_TEAM_PATH = "/nl/profile/team"
CONF_SESSION_COOKIE = "session_cookie"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

ATTRIBUTION = "Data provided by KNVB Rinus"
