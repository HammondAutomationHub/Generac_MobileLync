# Mobile Link Propane (Home Assistant)

A Home Assistant custom integration that logs into **Generac Mobile Link** (app.mobilelinkgen.com) and creates sensors for propane tank monitors.

## Features
- HACS installable
- Config Flow: prompts for email + password
- Discovers propane tanks and lets you select which ones to add
- Options Flow: change selected tanks and which sensors are created
- Entities per selected tank:
  - Propane level (%)
  - Last reading (timestamp) *(optional sensor)*
  - Capacity (gallons) *(optional sensor)*
  - Battery level *(optional sensor)*
  - Device status *(optional sensor)*
- Extra attributes on propane % sensor include device id/type and last reading.

## Install (HACS)
1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add your GitHub repo URL, Category: **Integration**
3. Install **Mobile Link Propane**
4. Restart Home Assistant
5. Settings → Devices & services → Add integration → **Mobile Link Propane**

## Notes / Disclaimer
This integration uses the same web/API endpoints the Mobile Link dashboard uses. API behavior may change without notice.

## Debugging
Enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.mobilelink_propane: debug
```

## Support
Open an issue in the repo and include:
- HA version
- Integration version
- Redacted debug log excerpt
