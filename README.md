# Mobile Link Propane (Home Assistant)

A Home Assistant custom integration to surface **propane tank level** from **Generac Mobile Link**.

## Why cookie-based auth?
Mobile Link can present interactive bot checks (CAPTCHA) during automated login. This integration avoids headless login and instead uses a **session cookie** you copy from your browser after logging in normally.

## Install (HACS)
1. HACS → Integrations → Custom repositories → add this repo (category: Integration)
2. Install **Mobile Link Propane**
3. Restart Home Assistant
4. Settings → Devices & Services → Add Integration → **Mobile Link Propane**

## Setup: Get your Cookie header
1. Sign in at **app.mobilelinkgen.com** in your browser
2. Open **DevTools → Network**
3. Click the request to: `/api/v2/Apparatus/list`
4. In **Request Headers**, copy the full `Cookie:` header value
5. Paste it into the integration setup

If the cookie expires, Home Assistant will prompt you to reauthenticate (paste a fresh cookie).

## Entities
For each selected tank, this integration creates:
- **Propane %** sensor (always)
Optional sensors (enable in Options):
- Last Reading (timestamp)
- Capacity (gal)
- Battery (text)
- Status (text)
