# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- The diagnostics download now hides the VPN check host and includes the VPN
  state.

### Changed

- Docs: the VPN check warns against using the WireGuard endpoint and its UDP
  port as target.
- `tools/probe_endpoints.py` is standalone: it needs only `aiohttp`, not Home
  Assistant.

### Changed

- Docs: step-by-step guide for the optional VPN check (getting started step
  12), troubleshooting rows, known limitations and the WireGuard handshake
  and reconnect ideas under planned.

## [0.4.0] - 2026-11-16

### Added

- VPN check: enter a DNS name, IPv4 or IPv6 address (and a TCP port) of a
  device behind a site-to-site tunnel in the options. The new binary sensor
  **VPN reachable** and the sensor **VPN latency** show whether the tunnel
  carries traffic. It works with every VPN type. A refused connection counts
  as reachable. The sample dashboard has a VPN pill that appears only when the
  check is set up.
- `tools/probe_endpoints.py`: a read-only probe that lists which further REST
  endpoints (VPN, firmware, DHCP, failover and others) a router offers. It
  prints names and types, never keys, addresses or other text values.

### Changed

- The sample dashboard `dashboards/teltonika-control.yaml` has a new look:
  coloured Bubble Card pills in two columns and Mushroom badges at the top.
  Wi-Fi first and Mobile first are two buttons that show the active priority,
  the priority drop-down is gone. Bubble Card (and optionally Mushroom) is
  needed for this dashboard only, not for the integration.
- Docs state that no Home Assistant helpers are required and add a
  step-by-step guide for an optional monthly data counter with the Utility
  Meter helper.

## [0.3.1] - 2026-11-16

### Changed

- New brand images: a router with antennas, Wi-Fi arcs and the text RUTx as
  icon, plus a logo with the name in a light and a dark variant. The artwork is
  original and drawn by `tools/make_brand_images.py`.
- The README states that the project is not affiliated with Teltonika Networks
  and describes how to run the tests on Linux or WSL.

## [0.3.0] - 2026-11-16

### Added

- Native Wi-Fi management entities: buttons **Scan for Wi-Fi networks**,
  **Add selected network** and **Remove selected network**, selects **Found
  networks** and **Saved networks**, a **Wi-Fi password** text entity (shows a
  mask only) and a **Last Wi-Fi action** sensor. Saved networks include the
  Multi AP list.
- **Router time** diagnostic sensor from the `Date` header of the router's
  answers (disabled by default, only when the header is present).
- Ready-made dashboard: sections for adding and removing Wi-Fi networks and
  for GPS. Guides updated.
- `tools/live_smoke_test.py` prints the field names of the device status, the
  GPS answer and the router clock.

### Fixed

- The Wi-Fi sensors (network, signal, band, speed) now describe the connection
  that carries the uplink. Before, the first connected entry was shown, which
  was wrong when the router was connected to the same network twice.

## [0.2.0] - 2026-11-16

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
