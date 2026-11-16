# Teltonika Control

Native Home Assistant integration for Teltonika RUTC and RUTX routers.
It talks to the RutOS REST API, so no Modbus, MQTT or router scripts are
needed.

It grew out of a camper setup: switch between Wi-Fi and mobile data, get told
when a hotspot needs a login, and restart things without opening the router
web page.

## Supported Routers

| Family | Examples | Status |
|---|---|---|
| RUTC | RUTC50 | Developed against a RUTC50 (RutOS 7.24) |
| RUTX | RUTX11, RUTX50, RUTX14 | Same API, not yet tested on hardware |

RUTC and RUTX use the same RutOS API (the published API description for both
families is identical). Modems, Wi-Fi radios and interfaces are read from the
router, not hard-coded, so differences such as which radio is 2.4 or 5 GHz do
not matter.

## Prerequisites

Check these before you add the integration. Most setup problems come from
the router side: the router must be reachable and the user must be allowed
to do what the integration does.

### Home Assistant

- Home Assistant 2025.2 or newer (developed and tested with 2026.10).
- The Home Assistant host must reach the router over the network, either on
  the router's LAN or routed to it. The integration polls the router; the
  router never connects to Home Assistant, and no cloud account is needed.
- HACS is optional and only needed for the HACS installation.

### Router

- A Teltonika RUTC or RUTX router running **RutOS 7**. The REST API
  description published for RUTC50 and RUTX starts at RutOS 7.9, and the
  integration was developed against 7.24. Routers on RutOS 6 are not
  supported.
- The router web interface must be reachable from the Home Assistant host,
  because the REST API is served by it. It uses HTTPS on port 443 by
  default, with a self-signed certificate. If Home Assistant is not on the
  router's LAN, allow the access under **System, Administration, Access
  Control, General** and in the firewall.
- Optional hardware decides which entities appear: a modem with a SIM for the
  mobile entities, a second SIM slot for the SIM select, and Wi-Fi for the
  Wi-Fi entities.
- For uplink priority and hotspot handling, at least one Wi-Fi network must
  be saved on the router as a Wi-Fi client. Without it the priority select
  is unavailable.

### Router User and Permissions

The integration signs in with a user name and password and receives a
session token. The token lasts as long as the router setting **API session
timeout** (System, Administration, General; default 300 seconds) and is
renewed automatically. Everything the integration does is checked against
the rights of that user's group, on every call.

Create a dedicated user for Home Assistant instead of using `admin`:

1. Under **System, Administration, User Settings** create a group for Home
   Assistant (or pick an existing one) with the rights listed below.
2. Create a user in that group and give it a strong, unique password.
3. Leave SSH access off for this user. The integration does not need it.

| Level | Rights | What works |
|---|---|---|
| Monitoring only | Read on the pages below | Sensors and binary sensors. Buttons, switches, selects and services fail with the router's error message. |
| Full control | Read and write on the pages below | Everything in this document. |
| Administrator | `admin` group | Works, but gives Home Assistant full control of the router. Not recommended. |

The pages are the router web interface pages that the API operations belong
to:

| Used for | Web interface page | Needs |
|---|---|---|
| Setup, model and firmware | System, Device, Info | Read |
| Uplink and priority state | Network, Interfaces | Read |
| Uplink priority, hotspot login mode | Network, Interfaces | Write |
| Wi-Fi client and access point state | Network, Wireless, SSIDs | Read |
| Access point switches, reconnect Wi-Fi, scan, save and remove networks | Network, Wireless, SSIDs | Write |
| Modem sensors | Network, Mobile | Read |
| Restart mobile connection, SIM slot | Network, Mobile, Modems | Write |
| Reboot router | System, Administration, General | Write |

Teltonika's API description does not list the exact permission entry for each
operation. The table maps operations to web interface pages as the API
description does. If an action is refused, Home Assistant shows the router's
error message; grant read or write on that page to the group and try again.

#### What the Integration Changes on the Router

Knowing this helps you decide how much to allow:

- Routing metric of the Wi-Fi client interfaces (0 for Wi-Fi first, 10 for
  mobile first), followed by a Wi-Fi reconnect.
- The on/off flag of the router's own access points.
- Saved Wi-Fi client networks (`join_wifi` and `forget_wifi`).
- Restart of the mobile connection, SIM slot switch and router reboot.

It never changes passwords, users, firewall rules or firmware.

#### Security Notes

- The password is stored in the Home Assistant config entry, like the
  credentials of any other integration. Diagnostics downloads redact it.
- RutOS can temporarily block an address after repeated failed logins. If
  setup keeps failing after wrong passwords, check **System, Administration,
  Access Control, Security** and unblock the Home Assistant host.
- Do not open the router web interface to the internet just for Home
  Assistant. Reach it over the LAN or a VPN.

## Installation

### HACS (custom repository)

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/BetaHydri/teltonika-control-ha` as type
   **Integration**.
3. Install **Teltonika Control** and restart Home Assistant.

### Manual

Copy `custom_components/teltonika_control` into the `custom_components`
folder of your Home Assistant configuration and restart.

## Setup

New to this? The [step-by-step guide](docs/getting-started.md) walks you from
the router user to your first dashboard card. The short version:

1. Make sure the [prerequisites](#prerequisites) are met, in particular the
   router user and its permissions.
2. In Home Assistant, go to **Settings, Devices & services, Add
   integration** and choose **Teltonika Control**.
3. Enter the router address, user and password. Leave **Verify SSL
   certificate** off if the router uses its self-signed certificate.

Use `http://` in front of the address to talk plain HTTP.

If the router address, user or password changes later, use **Reconfigure**
on the integration. A rejected password starts the re-authentication flow
automatically.

## What You Get

### Router

| Entity | Type | Notes |
|---|---|---|
| Uplink | sensor | `wifi`, `mobile`, `ethernet` or `other` |
| Uplink IP address | sensor | Diagnostic |
| Wi-Fi network, signal, link speed, band | sensors | Router as Wi-Fi client |
| Hotspot login | sensor | `no_wifi`, `idle`, `waiting`, `login_required`, `online` |
| Wi-Fi connected | binary sensor | Router is a Wi-Fi client |
| Internet | binary sensor | Result of the internet check |
| Hotspot login required | binary sensor | Wi-Fi is up but has no internet |
| Access point *name* | switch | The router's own Wi-Fi, real state |
| Uplink priority | select | Wi-Fi first or mobile first |
| Reconnect Wi-Fi | button | Reconnects all saved networks |
| Reboot router | button | Add a confirmation in your dashboard |

### Modem (one device per modem)

Operator, network type, band, RSRP, RSRQ, SINR, temperature, data connection,
SIM state, active SIM, data received and sent, a connected sensor, a
**Restart mobile connection** button and, on dual SIM modems, a **SIM slot**
select. RSSI and signal quality are disabled by default.

## Hotspots With a Login Page

Some free Wi-Fi networks need a click on a landing page. The router cannot do
that itself, but the login is valid for the whole router afterwards because
the hotspot only sees the router.

1. Call the service `teltonika_control.portal_mode` (or press your dashboard
   button for it). Wi-Fi gets priority and the integration waits.
2. On a phone connected to the router, open `http://neverssl.com` and accept
   the hotspot page.
3. As soon as the internet check passes, the router stays on Wi-Fi and the
   event `teltonika_control_portal_result` fires with `success: true`.
   Without internet after the wait time, the router goes back to mobile data
   and the event has `success: false`.

The **Hotspot login** sensor shows `login_required` while Wi-Fi is the uplink
but has no internet.

### Notification example

```yaml
automation:
  - alias: "Router: hotspot needs login"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_hotspot_login_required
        to: "on"
        for: "00:03:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: Hotspot login needed
          message: Open http://neverssl.com and accept the page.
```

Adjust the entity IDs to your router. The same pattern works for
`binary_sensor.*_wifi_connected` going to `off` for "Wi-Fi lost".

## Services

| Service | Purpose |
|---|---|
| `portal_mode` | Prefer Wi-Fi and wait for the hotspot login |
| `set_priority` | Wi-Fi or mobile first, optionally rolled back without internet |
| `scan_wifi` | Return nearby networks (response data) |
| `join_wifi` | Save a network as Wi-Fi client, or into the Multi AP list on a Multi AP radio; mobile stays preferred |
| `forget_wifi` | Remove a saved client network (`station_id`) or a Multi AP list entry (`ssid`) |

Each service takes the router as `device_id`.

### Multi AP radios

On some routers the 5 GHz radio runs as Multi AP (the RUTC50 does). The router
does not accept a normal Wi-Fi client there, so `join_wifi` for that radio adds
the network to the Multi AP list, or changes its password if the SSID is
already listed. The router allows only one client or one Multi AP per radio;
`join_wifi` tells you when a radio is taken. `forget_wifi` removes Multi AP
entries by `ssid`. The last entry of the list cannot be removed: an empty list
makes the router service restart every few seconds. Remove it in the router
web interface if you really want an empty list.

When a client network is removed, its network interface is removed too, unless
it is one of the router's default interfaces (`lan`, `wan*`, `mob*`, `vpn*`).

## Options

- **Update interval**: 10 to 600 seconds, default 30.
- **Internet check URL**: must answer HTTP 204 when the internet works.
  Leave empty to turn the check off.

The internet check runs on the Home Assistant host. It is only meaningful if
Home Assistant reaches the internet through this router.

## Known Limitations

- Saved Multi AP list entries are not shown as entities yet, and a Multi AP
  radio is not asked what it is currently connected to beyond the Wi-Fi
  client sensors.
- Changing the SIM drops mobile data for about a minute and is not rolled
  back automatically.
- Switching off the access point you are connected through disconnects you.
- Field names in the modem, Wi-Fi and interface answers differ slightly
  between RutOS releases. Open an issue with the diagnostics download if an
  entity stays empty.

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements_test.txt
.venv\Scripts\python -m pytest
```

An optional read-only check against a real router lives in
`tools/live_smoke_test.py`. It reads the address and login from the
environment variables `TELTONIKA_HOST`, `TELTONIKA_USER` and
`TELTONIKA_PASSWORD`.

## See Also

- [Step-by-step guide](docs/getting-started.md)
- [Teltonika API documentation](https://developers.teltonika-networks.com/)
- [Changelog](CHANGELOG.md)
