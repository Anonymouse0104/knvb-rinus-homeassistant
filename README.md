# KNVB Rinus – Home Assistant

Custom Home Assistant integration for **KNVB Rinus**.

The integration reads the authenticated Rinus team page and calendar and exposes team, season, training, match and player information in Home Assistant.

## What is included

- Season and team information
- Training schedule and next training
- Next match and opponent
- Full calendar/match data as entity attributes
- Player list
- Playing time per player and per match
- Formation, lineup and match status when Rinus provides them
- Clean HACS package with branding

## Authentication

Rinus uses a KNVB account session. This integration therefore uses the authenticated browser cookie rather than storing a KNVB password.

In Home Assistant go to **Settings → Devices & services → Add integration → KNVB Rinus** and paste the current Rinus `Cookie` request-header value from your browser's DevTools.

The cookie is stored in the Home Assistant config entry and is not committed to GitHub by this project.

If the cookie expires, open the integration options and replace it with a fresh cookie.

## HACS

Add this GitHub repository as a custom repository in HACS under **Integrations** and install **KNVB Rinus**.

After installation, restart Home Assistant and add the integration.

## Important

Rinus is a web application and does not provide a documented public API for this integration. The integration therefore reads the data that Rinus itself sends to the authenticated web client. Changes to the Rinus website can require updates to this integration.

## Data observed from Rinus

Rinus exposes calendar entries with fields such as `isTrainingDay`, `isMatchDay`, `date`, `type`, `training`, `match`, `event`, `rating` and `blueprint`. Match events can contain formation, match status, players, current lineup and `playingTime` values.

## License

MIT
