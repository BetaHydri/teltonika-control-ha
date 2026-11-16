# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Docs brought up to date: router clock source, required integration version
  for the sample dashboard, and the gentle polling and GPS filtering in the
  feature list.

## [0.6.1] - 2026-11-16

### Fixed

- The GPS sensors no longer jump to 0 satellites and 500 m accuracy for a
  single reading. The receiver of a RUTC50 now and then reports one empty
  reading between normal ones; up to three empty readings in a row are
  ignored and the last good values stay. A longer loss of the fix still shows
  up. This avoids false zone changes in automations.

## [0.6.0] - 2026-11-16

### Changed

- **Much gentler polling.** The integration used to ask the router for about
  11 pages at once every 30 seconds, which pushed the CPU of a RUTC50 to
  40 to 100 % while the router itself showed 3 % at rest. Now the pages are
  read one after the other, the status pages (uplink, Wi-Fi status, modem, GPS,
  load) on every update and the pages that rarely change (Wi-Fi configuration,
  radios, WireGuard instances, Multi AP list) only every 5 minutes. The DHCP
  clients are read at most every 2 minutes, a page that does not exist is
  asked again only after 5 minutes. Actions of the integration read everything
  again at once.

### Added

- New option **Configuration interval** (30 to 3600 seconds, default 300) next
  to the existing **Update interval**.

## [0.5.2] - 2026-11-16

### Fixed

- While the router's Wi-Fi status page does not answer, the Wi-Fi sensors no
  longer claim "unknown" or "no Wi-Fi": when a Wi-Fi interface carries the
  uplink, the name and band of the saved network are taken from the router
  configuration, **Wi-Fi connected** is on and the hotspot state follows the
  internet check. Signal and link speed stay unknown until the page answers.
- Sample dashboard: the Uplink badge falls back to the uplink type when the
  Wi-Fi name is unknown, and the speed badge shows a dash instead of
  "unknown Mbit/s".

## [0.5.1] - 2026-11-16

### Fixed

- One slow router page no longer takes every entity offline. Before, a
  timeout on any page (seen with the Wi-Fi status of a RUTC50) made the whole
  update fail and left all entities unavailable and the setup retrying. Now
  only the interface list is essential; every other page keeps its last known
  values when it does not answer, is asked again after two minutes (so a
  struggling router is not kept busy) and logs one warning.

### Changed

- Sample dashboard: adding a Wi-Fi network now follows three steps. After you
  choose a network, its pill is highlighted with a green border and offers
  the optional password and **Add**; before that a grey hint is shown.

## [0.5.0] - 2026-11-16

### Added

- WireGuard control: for every WireGuard instance a binary sensor for the
  interface state, a switch to enable or disable it, a **Reconnect WireGuard**
  button (off, wait, on) and traffic counters. Without the right to read the
  configuration, a tunnel is only watched, not switched.
- Router health sensors: uptime, CPU load, memory usage (flash usage is
  disabled by default) and **DHCP clients** with a list of the connected
  devices as attribute (no MAC addresses).
- The router clock now comes from the system usage status, with the `Date`
  header as fallback.
- All new endpoints are optional: if the router user may not read a page, the
  matching entities are simply not created.
- The sample dashboard has a **Restart WireGuard tunnel** pill and a **Router
  health** block. Docs: new setup step 13, permissions, troubleshooting.

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
