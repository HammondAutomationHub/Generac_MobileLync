# Generac Mobile Link Propane Monitor

A Home Assistant custom integration to monitor **Generac propane tank levels** via the Mobile Link cloud service.

## Features

- Propane tank level monitoring (percentage)
- Multiple tank support with per-tank selection during setup
- Optional diagnostic sensors for last reading, capacity, battery, and connection status
- Cookie-based authentication that works with Generac's anti-bot protections
- Automatic session expiry detection with persistent notification and guided re-authentication
- Options reload automatically when you change tanks or sensor settings

## Installation

### HACS (recommended)

1. Add this repository as a custom HACS repository.
2. Install **Mobile Link Propane**.
3. Restart Home Assistant.

### Manual

1. Copy the `mobilelink_propane` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Generac Mobile Link Propane**.
3. Enter your Mobile Link username (email).
4. Follow the guided login steps:
   - Open [app.mobilelinkgen.com](https://app.mobilelinkgen.com) and log in (complete any CAPTCHA).
   - Open browser Developer Tools (F12) → **Network** tab.
   - Refresh the page.
   - Copy the **Cookie** request header from any request to `app.mobilelinkgen.com`.
   - Paste it into Home Assistant. Raw cookie values, `Cookie: ...` lines, copied header blocks, and curl commands are all accepted.
5. Select which propane tanks to add.
6. Optionally enable extra sensors under **Configure**.

## When Your Cookie Expires

Cookies typically last several weeks to months. When a session expires:

- The integration shows a **persistent notification** in Home Assistant.
- The integration card offers **Reconfigure** to paste a fresh cookie.

## Options

From the integration card, choose **Configure** to:

- Change which tanks are monitored
- Enable or disable optional sensors (last reading, capacity, battery, status)

Changes apply immediately after saving.

## Important Notes

- This integration monitors **propane tanks only** (Mobile Link apparatus type 2).
- Generator monitoring is not included in this integration.
- Due to Generac's anti-bot protections, the guided cookie method is the most reliable authentication approach.

## Support

Report issues on [GitHub](https://github.com/HammondAutomationHub/Generac_MobileLync/issues).
