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
4. Follow the cookie steps below.
5. Select which propane tanks to add.
6. Optionally enable extra sensors under **Configure**.

## How to copy your Mobile Link cookie (Developer Tools)

These steps are based on a captured browser session to the Mobile Link dashboard. The integration validates your cookie against the same API call the website uses to load your tanks.

### Before you start

- Use **Chrome** or **Edge** on a computer.
- Log in at [app.mobilelinkgen.com](https://app.mobilelinkgen.com).
- Complete any CAPTCHA.
- Wait until the **dashboard shows your propane tank card(s)**. If no tanks appear, fix that in Mobile Link first.

### Step 1 — Open Developer Tools

1. Press **F12** (or right-click → **Inspect**).
2. Open the **Network** tab.
3. Click **Fetch/XHR** to hide images, CSS, fonts, and scripts.

### Step 2 — Refresh once (recommended)

1. Optional: enable **Preserve log**.
2. Press **Ctrl+R** to refresh the dashboard.
3. Wait for the tank card(s) to load.

This keeps the request list short and makes the correct API call easier to find.

### Step 3 — Select the correct request

In the Network list, find the request named **`list`** whose URL is:

```text
https://app.mobilelinkgen.com/api/v2/Apparatus/list
```

| Select this | Do not select |
|-------------|---------------|
| `list` → `/api/v2/Apparatus/list` | `dashboard` (HTML page) |
| Method: **GET** | CSS, JS, fonts, images |
| Status: **200** | `Account`, `Subscription`, `MessageCenter` |
| Type: **fetch/xhr** | Google Analytics / telemetry calls |

**Tip:** Type `Apparatus` in the Network filter box if the list is long.

### Step 4 — Confirm the response is correct

With `list` selected:

1. Open **Headers** and verify:
   - **Request URL:** `https://app.mobilelinkgen.com/api/v2/Apparatus/list`
   - **Request Method:** `GET`
   - **Status Code:** `200`
2. Open **Preview** or **Response** and confirm JSON like:
   - `"name": "House Propane"` (your tank name)
   - `"FuelLevel": 50`
   - `"type": 2`

If you see HTML or a login page instead of JSON, your session is not valid. Log in again and repeat.

### Step 5 — Copy the cookie

Still on the **Headers** tab, scroll to **Request Headers** and find **`cookie`**.

**Option A (recommended):** Copy the full cookie value — the long text after `cookie:`.

**Option B:** Right-click the `list` request → **Copy** → **Copy as cURL**, then paste the entire curl command into Home Assistant.

Home Assistant accepts any of these formats:

- Raw cookie value: `part1=value1; part2=value2; ...`
- Header line: `Cookie: part1=value1; part2=value2; ...`
- Full copied request headers
- A curl command containing `-H 'Cookie: ...'`

### Step 6 — Paste into Home Assistant

Paste into the integration setup screen and submit. The integration will call `/api/v2/Apparatus/list` with your cookie to verify it works.

## Troubleshooting cookie setup

| Problem | What to try |
|---------|-------------|
| Cannot find `Apparatus/list` | Make sure you are on `/dashboard`, enable **Fetch/XHR**, refresh once |
| Request status is 401/403 | Log in again and copy a fresh cookie |
| Response is HTML, not JSON | Session expired or wrong request selected |
| Cookie copied from Application tab does not work | Copy from the **`list` request headers**, not individual cookies |
| Setup says no tanks found | Confirm Preview shows `"type": 2` apparatus in the JSON |
| Exported HAR file has empty cookies | Normal — use live DevTools instead of a saved HAR |

## When Your Cookie Expires

Cookies typically last several weeks to months. When a session expires:

- The integration shows a **persistent notification** in Home Assistant.
- The integration card offers **Reconfigure** to paste a fresh cookie.

Use the same `/api/v2/Apparatus/list` steps above when re-authenticating.

## Options

From the integration card, choose **Configure** to:

- Change which tanks are monitored
- Enable or disable optional sensors (last reading, capacity, battery, status)

Changes apply immediately after saving.

## Important Notes

- This integration monitors **propane tanks only** (Mobile Link apparatus `type: 2`).
- Generator monitoring is not included in this integration.
- Mobile Link uses Auth0 session cookies. They are usually **HttpOnly**, so copying the combined `cookie` header from the `list` API request is the reliable method.

## Support

Report issues on [GitHub](https://github.com/HammondAutomationHub/Generac_MobileLync/issues).
