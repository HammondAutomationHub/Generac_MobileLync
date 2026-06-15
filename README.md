# Generac Mobile Link Propane Monitor

A Home Assistant custom integration to monitor **Generac propane tank levels** and generator status via Mobile Link.

## Features

- Monitors propane tank levels (percentage and gallons)
- Generator status and runtime tracking
- Battery voltage monitoring
- Multiple tank support
- Automatic detection of expired sessions with guided renewal
- Clean re-authentication flow

## Setup Instructions

### Step 1: Install the Integration

1. Copy the `mobilelink_propane` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **"Generac Mobile Link Propane"**.

### Step 2: Initial Configuration

1. Enter your **Mobile Link username** (email).
2. Click **Submit**.
3. Follow the guided instructions:
   - Open the Mobile Link login page.
   - Log in normally in your browser (handle CAPTCHA).
   - Copy the full **Cookie** header from Developer Tools (Network tab).
   - Paste it back into Home Assistant.

## When Your Cookie Expires

The integration automatically detects expired cookies and shows a **persistent notification** with a direct link to the renewal flow.

## Important Notes

- Due to Generac's anti-bot protections, this guided cookie method is the most reliable approach.
- Cookies usually last several weeks to months.

Enjoy monitoring your propane levels! ⛽
