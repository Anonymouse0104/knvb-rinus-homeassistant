# KNVB Rinus – Home Assistant

Custom Home Assistant integration for **KNVB Rinus**.

The integration reads the authenticated Rinus calendar and team pages and exposes them as Home Assistant entities. It does **not** use the temporary Next.js build ID or GraphQL calls; it loads the normal Rinus page and extracts the `__NEXT_DATA__` payload. The supplied Rinus calendar response confirmed that this payload contains the season, 161 calendar items and detailed match information.

## What it provides

- Current season
- Active team name and team data
- Next match date/time
- Next opponent
- Match type and home/away status
- Formation, score and player list for the next match
- Next scheduled training
- A Home Assistant calendar containing matches and trainings
- Team information as sensor attributes
- Automatic polling every 15 minutes
- Re-authentication when the Rinus session expires

## Important: authentication

Rinus does not expose a public API for this integration. The current implementation therefore uses the user's own authenticated `CraftSessionId` session cookie. The cookie is stored in the Home Assistant config entry and is never logged by the integration.

### Get your CraftSessionId

1. Log in to https://rinus.knvb.nl in Chrome.
2. Press `F12`.
3. Open **Application** → **Cookies** → `https://rinus.knvb.nl`.
4. Find the cookie named **CraftSessionId**.
5. Copy only its **Value**.
6. In Home Assistant, add **KNVB Rinus** and paste that value.

**Never post the cookie in GitHub, screenshots, chat or an issue. It is an active login credential.**

## Install with HACS

1. Add this repository as a **Custom repository** in HACS.
2. Select category **Integration**.
3. Install **KNVB Rinus**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Search for **KNVB Rinus**.
7. Enter your own `CraftSessionId` value.

## Manual installation

Copy:

```text
custom_components/rinus_knvb
```

to:

```text
/config/custom_components/rinus_knvb
```

Restart Home Assistant and add the integration through the UI.

## Entities

The first version creates a Rinus device with these entities:

- `sensor.rinus_knvb_seizoen`
- `sensor.rinus_knvb_volgende_wedstrijd`
- `sensor.rinus_knvb_volgende_tegenstander`
- `sensor.rinus_knvb_volgende_training`
- `sensor.rinus_knvb_team`
- `calendar.rinus_knvb_kalender`

The match sensors include useful attributes such as match ID, opponent, match date/time, type, home/away, formation, score, player list and current lineup.

## Security note

A `CraftSessionId` is a session credential. Treat it like a password. If it is accidentally exposed, log out of Rinus / invalidate the session and create a new session before using the integration again.

## Current limitation

The integration intentionally starts with read-only data. It does not create or modify matches, trainings, lineups or player data in Rinus.

The exact data model is based on the authenticated Rinus calendar/team responses captured during development. Rinus is a web application rather than a documented public API, so future website changes may require updates to the parser.
