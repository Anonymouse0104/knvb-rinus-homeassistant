# KNVB Rinus – Home Assistant

Custom Home Assistant integration for **KNVB Rinus**.

The integration reads the authenticated Rinus team profile and calendar and exposes team, season, training, match and player information in Home Assistant.

## Features

- Season and team information
- Training schedule and next training
- Next match and opponent
- Match count and detailed match entities
- Player count and one entity per known player
- Playing minutes per player
- Per-player match history
- Match players, line-up, formation and status when supplied by Rinus
- Raw Rinus data preserved in entity attributes where practical
- HACS-compatible package with KNVB Rinus branding

## Authentication – Cookie instructions

Rinus does not provide a documented public API for this integration. The integration uses your authenticated Rinus browser session.

**You must provide the complete `Cookie` request-header value. Do not use `Set-Cookie`.**

### Get the Cookie from Chrome or Edge

1. Open **https://rinus.knvb.nl/** and make sure you are logged in.
2. Press **F12** to open Developer Tools.
3. Open the **Network** tab.
4. Reload the Rinus page if necessary.
5. In the Network list, open a request to `rinus.knvb.nl`. A request such as `profile` is suitable.
6. Open **Headers**.
7. Scroll to **Request Headers**.
8. Find **Cookie**.
9. Right-click the Cookie value and choose **Copy value**.
10. Paste that **entire value** into the KNVB Rinus configuration screen in Home Assistant.

The endpoint `/api/modals/get/team/profile` is one of the authenticated endpoints used by the Rinus web client and is a useful request to inspect.

### Important: Cookie vs Set-Cookie

Use:

`Request Headers → Cookie`

Do **not** use:

`Response Headers → Set-Cookie`

The Cookie header contains the complete browser session information required by the integration.

### Security

The Cookie header is sensitive authentication information. **Never paste it into GitHub, GitHub Issues, screenshots, forum posts or support requests.** Treat it like a password.

If the session expires, repeat the steps above and replace the cookie through the integration options.

## HACS installation

Add this repository as a custom repository in HACS under **Integrations**:

`https://github.com/Anonymouse0104/knvb-rinus-homeassistant`

Install **KNVB Rinus**, restart Home Assistant, then add the integration under **Settings → Devices & services**.

## Data exposed

The integration keeps the Rinus payload available in Home Assistant attributes where possible. Depending on what Rinus currently returns, this can include:

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

Rinus can change its web/API structure without notice. If the website changes, some fields may temporarily become unavailable and an update to this integration may be required.

## Version

Current version: **0.3.0**

## License

MIT
