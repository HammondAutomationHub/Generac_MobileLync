# Generac Mobile Link Propane Monitor

A Home Assistant custom integration to monitor **Generac propane tank levels** via the Mobile Link cloud service.

## Features

- Propane tank level monitoring (percentage)
- Multiple tank support with per-tank selection during setup
- Propane level sensor for each selected tank (always created)
- Battery sensor for each tank (always created; Mobile Link reports values like `good`)
- Optional diagnostic sensors for last reading, capacity, and connection status
- Cookie-based authentication that works with Generac's anti-bot protections
- Automatic session expiry detection with persistent notification and guided re-authentication
- Proactive cookie refresh reminders with configurable estimated lifetime
- Options reload automatically when you change tanks or sensor settings
- Generac branding in Home Assistant (integration icon and device pages)

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

## Branding

The integration ships with the official Generac logo in `custom_components/mobilelink_propane/brand/`. Home Assistant **2026.3+** shows it automatically on:

- **Settings → Devices & Services** (integration tile)
- The Mobile Link service device page
- Linked propane tank device pages

To use your own image, replace `brand/icon.png` (square, 256×256 recommended) and restart Home Assistant.

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

### Step 3 — Select the best request

**Best choice (verify tanks before setup):**

```text
Name:   list
URL:    https://app.mobilelinkgen.com/api/v2/Apparatus/list
Status: 200
Preview: JSON with "FuelLevel" and your tank name
```

**Also acceptable (cookie only):**

```text
Name:   Account
URL:    https://app.mobilelinkgen.com/api/v1/Account/
Status: 200
Preview: JSON with your name and email
```

The cookie is identical on both requests. Use `Account/` only if you cannot find `Apparatus/list`, but you will not be able to confirm tank data until Home Assistant setup runs.

**Avoid:**

| Request | Why |
|---------|-----|
| `/api/v1/Subscription/payment/...` | Status **204** — no response body |
| `dashboard` | HTML page, not an API call |

### Step 4 — Copy the full cookie value

On **Headers** → **Request Headers** → **`cookie`**, copy the **entire** value.

A valid Mobile Link cookie includes **all** of these parts:

```text
visid_incap_...=...
nlbi_...=...
.AspNetCore.Cookies=chunks-2
.AspNetCore.CookiesC1=...   (very long — do not truncate)
.AspNetCore.CookiesC2=...   (very long — do not truncate)
incap_ses_...=...
```

**Common mistake:** copying only part of `.AspNetCore.CookiesC1`. The auth cookie is split across `C1` and `C2` — you need both.

**Easier option:** right-click the request → **Copy** → **Copy as cURL**, then paste the whole command into Home Assistant.

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

Mobile Link does not expose an exact session expiry time. This integration estimates it from when you last pasted the cookie.

### After expiry

When a session actually expires:

- The integration shows a **persistent notification** in Home Assistant.
- The integration card offers **Reconfigure** to paste a fresh cookie.

Use the same `/api/v2/Apparatus/list` steps above when re-authenticating.

### Proactive refresh reminder (v2.2.0+)

Before the estimated expiry, the integration can warn you early:

| Entity | Purpose |
|--------|---------|
| `sensor.*_cookie_age` | Days since the cookie was last updated |
| `sensor.*_cookie_refresh_by` | Estimated refresh-by timestamp |
| `binary_sensor.*_cookie_refresh_due` | Turns on when inside the warning window |

Defaults:

- **Estimated cookie lifetime:** 30 days
- **Warn before expiry:** 3 days

Adjust these under **Configure** on the integration card. When the warning window starts, Home Assistant shows a **Cookie refresh recommended** notification.

Example automation:

```yaml
alias: Mobile Link cookie refresh reminder
trigger:
  - platform: state
    entity_id: binary_sensor.mobile_link_jason_hammond_gmail_com_cookie_refresh_due
    to: "on"
action:
  - service: notify.notify
    data:
      message: "Mobile Link cookie may expire soon. Reconfigure the integration and paste a fresh cookie."
```

If you upgrade from an older version, the cookie timer starts when you update. Reconfigure once with your current cookie to reset the timer from a known-good session.

## Options

From the integration card, choose **Configure** to:

- Change which tanks are monitored
- Enable or disable optional sensors (last reading, capacity, status)
- Set estimated cookie lifetime and warning lead time

Changes apply immediately after saving.

## Important Notes

- This integration monitors **propane tanks only** (Mobile Link apparatus `type: 2`).
- Generator monitoring is not included in this integration.
- Mobile Link uses Auth0 session cookies. They are usually **HttpOnly**, so copying the combined `cookie` header from the `list` API request is the reliable method.

## Support

Report issues on [GitHub](https://github.com/HammondAutomationHub/Generac_MobileLync/issues).
