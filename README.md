# KNVB Rinus – Home Assistant

Custom Home Assistant integration for **KNVB Rinus**.

The integration reads the authenticated Rinus team profile API and calendar and exposes team, season, training, match and player information in Home Assistant.

## What is included

- Season and team information
- Club and team metadata
- Training schedule and next training
- Next match and opponent
- Full calendar/match data as entity attributes
- Player list
- Playing time per player and per match when Rinus provides it
- Formation, lineup and match status when Rinus provides them
- HACS package with KNVB Rinus branding

## Installation with HACS

1. Open **HACS → Integrations**.
2. Search for **KNVB Rinus** or add this repository as a custom repository:
   `https://github.com/Anonymouse0104/knvb-rinus-homeassistant`
3. Install **KNVB Rinus**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → KNVB Rinus**.

## Authentication – finding the Cookie header

KNVB Rinus does not provide a documented public API login for this integration. The integration therefore uses the active browser session from your logged-in Rinus account.

You must paste the **complete `Cookie` request-header value** into the Home Assistant configuration form.

### Chrome / Chromium

1. Log in to **Rinus** in Chrome.
2. Open your Rinus team/profile page.
3. Press **F12** to open Developer Tools.
4. Open the **Network** tab.
5. Reload the page if necessary.
6. Find the request named **`profile`**. For the current Rinus website this request is:
   `GET https://rinus.knvb.nl/api/modals/get/team/profile`
7. Click the **`profile`** request.
8. Open **Headers**.
9. Scroll to **Request Headers**.
10. Find the line named **`Cookie`**.
11. Right-click the value next to `Cookie` and choose **Copy value**.
12. Paste the **entire copied value** into the `Cookie` field in Home Assistant.

### Do not use `Set-Cookie`

There are two similarly named headers that can be confusing:

- **Correct:** `Request Headers → Cookie` ✅
- **Wrong:** `Response Headers → Set-Cookie` ❌

The integration needs the complete `Cookie` request header, not just `CraftSessionId` and not the `Set-Cookie` response header.

### Security warning

The Cookie header contains active session information for your Rinus account. Treat it like a password:

- Do **not** post it on GitHub.
- Do **not** put it in a public issue.
- Do **not** share it with other people.
- Do **not** paste it into chat when asking for support.

The cookie is stored in the Home Assistant config entry and is not included in this repository.

If your Rinus session expires, repeat the steps above and replace the cookie through the integration options/configuration.

## What the integration currently uses

The authenticated team information is retrieved from the endpoint used by the Rinus web application:

`/api/modals/get/team/profile`

This response currently contains team information, season information and the training schedule. The calendar endpoint is used for match information.

Rinus is a web application and does not provide a documented public API for this integration. Changes to the Rinus website can therefore require updates to this integration.

## Development

The integration lives under:

`custom_components/knvb_rinus/`

Do not commit personal Rinus cookies, session tokens or other authentication data to GitHub.

## License

MIT
