# KNVB Rinus – Home Assistant

Custom Home Assistant integration for **KNVB Rinus**.

The integration reads the authenticated Rinus team profile and calendar and exposes team, season, training, match and player information in Home Assistant.

## Features

- Season and team information
- Training schedule and next training
- Next match and opponent
- Match count and dynamic match entities
- Player count and one entity per current team player
- New players added in Rinus are detected automatically on the next refresh
- Players removed from the Rinus team roster are removed automatically
- Individual player entities use the `mdi:account` icon
- Playing minutes per player
- Per-player match history
- Match players, line-up, formation and status when supplied by Rinus
- Connection/status sensor showing whether the last update succeeded
- Automatic polling; configurable at 5, 10, 15, 30 or 60 minutes
- Diagnostics support with authentication data redacted
- HACS-compatible package with KNVB Rinus branding

## Authentication – Cookie instructions

Rinus does not provide a documented public API for this integration. The integration uses your authenticated Rinus browser session.

**You must provide the complete `Cookie` request-header value. Do not use `Set-Cookie`.**

### Get the Cookie from Chrome or Edge

1. Open **https://rinus.knvb.nl/** and make sure you are logged in.
2. Press **F12** to open Developer Tools.
3. Open the **Network** tab.
4. Reload Rinus if necessary.
5. Open a request to `rinus.knvb.nl`. A request such as `team.json` or `profile` is suitable.
6. Open **Headers**.
7. Scroll to **Request Headers**.
8. Find **Cookie**.
9. Right-click the Cookie value and choose **Copy value**.
10. Paste the **complete value** into the KNVB Rinus configuration screen.

### Important: Cookie vs Set-Cookie

Use:

`Request Headers → Cookie`

Do **not** use:

`Response Headers → Set-Cookie`

The Cookie header is sensitive authentication information and must never be published.

## Automatic refresh

The default refresh interval is **15 minutes**. In the integration options you can select:

- 5 minutes
- 10 minutes
- 15 minutes
- 30 minutes
- 60 minutes

When the Rinus session expires, the integration keeps the last successfully fetched data and reports the connection failure through the **Verbinding** sensor and Home Assistant logs. Replace the cookie through the integration options to restore updates.

## Dynamic players and matches

The current team roster is read from the authenticated Rinus team profile (`team[].players`). This means players do not have to appear in a match before they can be exposed in Home Assistant.

The integration also creates match entities dynamically from the Rinus calendar. Newly added matches are picked up during the next refresh without restarting Home Assistant.

## Data exposed

Depending on what Rinus currently returns, data can include:

- team IDs, club, age group and season
- training days, times, duration and field size
- match date/time, opponent, match type and status
- formation and current line-up
- players attached to a match
- player IDs/names
- playing time per match
- accumulated playing time per player
- player match history
- calendar item information

## Diagnostics

Home Assistant diagnostics can be used when reporting an issue. Authentication information such as cookies, session identifiers, tokens and authorization headers is redacted before diagnostics are returned.

**Never paste your Cookie header into GitHub Issues, screenshots, forums or chat.**

## HACS installation

Add this repository as a custom repository in HACS under **Integrations**:

`https://github.com/Anonymouse0104/knvb-rinus-homeassistant`

Install **KNVB Rinus**, restart Home Assistant, then add the integration under **Settings → Devices & services**.

## Version

Current version: **0.4.0**

## License

MIT
