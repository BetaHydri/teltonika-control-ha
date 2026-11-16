# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Config flow with re-authentication, reconfiguration and options.
- Sensors for uplink, Wi-Fi client, hotspot login state and modem signal.
- Binary sensors for Wi-Fi, internet, hotspot login and mobile data.
- Switches for the router's own access points with the real on/off state.
- Buttons to restart mobile data, reconnect Wi-Fi and reboot the router.
- Selects for uplink priority and the SIM slot of dual SIM modems.
- Services to wait for a hotspot login, set the priority and manage Wi-Fi
  networks.
- Diagnostics with personal data removed.
- English and German translations.
- Step-by-step guide in `docs/getting-started.md`.
- Ready-made dashboard in `dashboards/teltonika-control.yaml` with a guide in
  `docs/dashboard.md`.
- GPS: a position device tracker and sensors for speed, altitude, satellites,
  accuracy, heading and fix status, only on routers that provide GPS.
- Services accept a service target: the router device or any entity of the
  router (also a modem entity). `device_id` in the data keeps working.
- `join_wifi` saves networks of a Multi AP radio (5 GHz on the RUTC50) in the
  Multi AP list and refuses a radio that already has a client or Multi AP.
- `forget_wifi` removes Multi AP list entries by `ssid` (never the last one)
  and removes the interface of a forgotten client unless it is a default one.
