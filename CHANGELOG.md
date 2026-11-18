# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Sample dashboard.** The **SMS on the router** pill opens a **Send SMS**
  pop-up (Bubble Card) with the number and text fields and a Send button that
  asks for confirmation, so SMS can be sent without leaving the main dashboard.

## [0.15.0] - 2026-11-18

### Added

- **Send an SMS from the dashboard.** The text fields **SMS number** and
  **SMS text**, the button **Send SMS** and the sensor **SMS send result** let
  you write and send an SMS without an automation. The text is cleared after a
  successful send, the result says `Sent` or why it was not sent. Only on routers
  with the SMS page. A ready dashboard is `dashboards/teltonika-sms.yaml`.
- **Docs.** New automation examples: SMS from a button, sending the typed SMS
  from a script, and commands by SMS with a sender check.

## [0.14.0] - 2026-11-18

### Added

- **Tailscale, OpenVPN, IPsec and SSTP.** Each instance of these VPN types on
  the router gets a *connected* binary sensor (with the status text and
  counters as attributes), an *enabled* switch to connect or disconnect and a
  *Reconnect* button that switches the instance off and on. Based on Teltonika's
  API description; not yet tried on real hardware. Tailscale log out is
  deliberately not offered.

### Fixed

- **Firmware.** A router without a stable channel reports the placeholder
  `newest` as its stable version. The firmware entity now falls back to the
  newest release instead of treating the placeholder as a version.

## [0.13.0] - 2026-11-18

### Added

- **Found on the network.** A Teltonika router that asks for an address shows
  up under *Discovered* (MAC address ranges `20:97:27` and `00:1E:42`, the same
  as the core integration). Enter the login and the router is set up. A router
  that is already set up is not offered again; if its address changes and the
  old address no longer answers, the new one is taken over. An address that
  still answers is never replaced, because a router can be seen on several
  addresses.
- **MAC addresses in the device registry.** The router device carries its two
  MAC addresses, so Home Assistant can link it to the same device in other
  integrations.
- **HTTPS, then HTTP.** An address without `http://` or `https://` is tried with
  HTTPS first and then with plain HTTP, so a router that serves only HTTP can be
  set up (also through *Reconfigure* and discovery) without typing the scheme.
- **SMS.** The service `teltonika_control.send_sms` sends an SMS through a
  modem of the router and returns how many SMS parts it used. The sensor **SMS
  messages** counts the messages on the router, and every new message fires the
  event `teltonika_control_sms_received` with sender, text, date, modem and
  status. Messages already on the router at startup are not announced. The
  number and the text are never written to the log, and the texts are not
  stored in a sensor. New permission rows are in the README.
- **Firmware.** An update entity shows the installed firmware and the newest
  stable release the router found at its update server. It only informs. The
  versions are compared by their numbers; if they cannot be compared, it says
  "up to date". It appears only when the router has update information.
- **Sample dashboard:** two optional pills under *Router health*, **SMS on the
  router** and **Firmware**, which hide themselves while the data is missing.
- **Probe tool:** also asks for the firmware update information, the speed test
  state, VRRP, DDNS and the hotspot state, and shows firmware versions, message
  dates and speed test values (no names, numbers or message texts).

## [0.12.4] - 2026-11-18

### Added

- **The Wi-Fi scan says it has started.** **Last Wi-Fi action** now shows
  `Scanning for networks ...` as soon as you press **Scan for Wi-Fi networks**
  and replaces it with the result when the scan is done. Before, the pill showed
  the old result for the several seconds a scan takes, so it looked as if
  nothing happened. Pressing the button again while a scan runs is ignored
  instead of starting a second scan.

### Changed

- **Sample dashboard: controls are recognisable without the colour.** Every
  pill that does something has a small button on its right: a hand for a
  one-time action, a switch for data roaming (on or off), a filled or empty
  circle for Wi-Fi first and Mobile first, and the text On or Off for the
  router's own Wi-Fi. The small button does the same as the pill, including the
  confirmation. The roaming pills are now called "SIM 1: roaming on" and "off"
  so that the text fits beside the switch. See
  [docs/dashboard.md](docs/dashboard.md).

## [0.12.3] - 2026-11-18

### Changed

- Documentation only, no change to the integration code. The data volume
  warning in the automation examples no longer sends a message after a restart
  of Home Assistant (the sensor changes from `unknown` to its value, which
  counted as crossing the threshold) and no longer fails while the reset time
  is not known yet. The README describes the detection of an expired hotspot
  login and has a one-click button that opens the repository in HACS.
- The release is made from a repository history without the Co-authored-by
  lines of earlier commits. The tags `v0.12.1` and `v0.12.2` are protected by
  GitHub and still point to the old commits; the code is the same.

## [0.12.2] - 2026-11-17

### Fixed

- **Expired hotspot login is detected.** A hotspot that asks for a new login
  (for example every 24 hours) fails the failover check of the Wi-Fi, and the
  router then sends the traffic over mobile data. The internet check of Home
  Assistant still passed, so **Hotspot login** never showed `login_required`
  and the notification did not come. It now also shows `login_required` when
  the Wi-Fi is connected and the failover calls every Wi-Fi interface offline.
  Portal mode reads the failover state on every poll, so it notices the login
  without the usual delay.
- **Failover `standby` counts as online.** The router reports an interface
  that works but is not in use (the backup while another carries the traffic)
  as `standby`. It was read as not online, so **Failover mobile online** showed
  off, and the dashboard pill "Mobile offline", while Wi-Fi was the uplink and
  mobile data was fine. `standby` is now online; `offline` stays offline, and
  `starting` or `notracking` say nothing.

## [0.12.1] - 2026-11-17

### Fixed

- **The Uplink sensor follows the failover.** It showed the interface with the
  best metric even when the router's failover reported it offline, so a Wi-Fi
  whose hotspot blocks the check pings showed as the uplink while the traffic
  went over mobile data. Now an interface that the failover calls offline is
  passed over (attribute `failover_skipped`). If all interfaces are offline,
  the metric decides as before.
- **GPS without a fix.** The position now stays at the last known one instead
  of turning `unknown`, also across a restart of Home Assistant. The satellite
  sensor shows 0 instead of `unknown` when the receiver has no fix.

### Added

- **GPS signal** binary sensor: on while the receiver has a fix. Attributes:
  satellites in use and the time of the last fix. The device tracker gets the
  attributes `fix` and `last_fix`.

## [0.12.0] - 2026-11-17

### Added

- **Mobile data plan option.** In the options you can enter the monthly volume
  of your mobile contract in GB. The percentage, the **Data limit** sensor, the
  **Data limit reached** sensor and the dashboard pills then refer to your
  plan instead of the router's data limit. This fits providers that slow the
  connection down when the volume is used up: the router's limit can be set
  high, so that the router never switches the mobile data off, and only keeps
  the count. Without the option nothing changes. The plan counts 1 GB as
  1000 MB, the router's limit counts 1 MB as 1,048,576 bytes; the README
  explains the difference.

## [0.11.0] - 2026-11-17

### Added

- **Traffic rule switches.** One switch **Firewall rule *name*** for every rule
  in `/firewall/traffic_rules/config` that turns the rule on or off. Only the
  `enabled` field is written, and the setting is read back after the change,
  like the port forward switches. The attributes say what the rule does:
  `kind`, `group`, `source_zone`, `destination_zone`, `protocol`, `ports`,
  `action`. The router's own rules (named `Allow-...`, group `system`) are
  created **disabled**, because switching one off by accident can cut a
  connection; enable the ones you want in the entity settings.
- **Firewall counters.** **Open port forwards** and **Firewall rules open to the
  internet** count what is on, and list the names in the attribute `rules`, for
  example for a warning when something stays open.
- **Firewall dashboard.** A separate dashboard for the port forwards and traffic
  rules, `dashboards/teltonika-firewall.yaml`, with a guide in
  `docs/firewall-dashboard.md`: the rules of the router are listed by
  themselves, grouped into port forwards, access to the router from the
  internet and forwarding to the network. Every switch asks for confirmation.
  It needs the Mushroom and auto-entities frontend cards. The guide also shows
  a version without auto-entities, a pop-up version and an automation that
  warns when a port stays open.
- The port forward switches have the attribute `kind` (`port_forward`), which
  the firewall dashboard uses to find them.

### Changed

- The main sample dashboard no longer has a pill for one port forward. It has a
  **Firewall** pill that opens the firewall dashboard, green while nothing is
  open to the internet and orange while a port forward or a rule is on. It only
  appears while the router has such rules.

### Fixed

- Home Assistant logged a deprecation warning when a service was used:
  `DeviceEntry.config_entries` is replaced by `config_entry_id`. The service
  target now uses the new attribute and keeps working on older versions.

### Notes

- The traffic rules page is optional like the other new pages: a router or user
  without it gets no firewall rule entities and everything else keeps working.

## [0.10.1] - 2026-11-17

### Added

- **Failover by kind.** One binary sensor per kind of uplink that exists in
  the router's failover configuration: **Failover mobile online**, **Failover
  Wi-Fi online** and **Failover Ethernet online**. Each is on while any
  interface of that kind is online. The entity has the same name on every
  router, so dashboards and automations need no interface names.

### Fixed

- The failover entities now read what each interface is from the router's
  failover configuration (`/failover/interfaces/config`: type `mobile`,
  `wireless` or `wired`, and the interface name). A RUTC50 lists its Wi-Fi
  networks there as `wan2` and `wan3`; 0.10.0 named them by these IDs and could
  not tell that they are Wi-Fi. They are now called for example "Wi-Fi
  (wifi4)". The entity IDs of existing entities do not change.
- Docs: the router's failover check pings its check addresses through the
  interface, so a Wi-Fi network that blocks these pings shows `offline` while
  it carries traffic. The README says so, and the sample dashboard has no
  Wi-Fi failover pill.

### Changed

- The sample dashboard's failover pill uses **Failover mobile online** and no
  longer contains an interface name.

## [0.10.0] - 2026-11-17

### Added

- **Failover state.** For every interface in the router's failover
  configuration a sensor **Failover *interface*** (the router's text: online,
  offline, standby, starting, notracking; attributes health score, seconds
  since the last change, seconds online and offline and lost tracking probes)
  and a binary sensor **Failover
  *interface* online**. Read from `/failover/status`, which answers with a
  dictionary keyed by interface name.
- **Mobile data limit.** For each mobile interface with an enabled limit on
  the router: used data, limit, used percent, reset time and a binary sensor
  **Data limit reached**. Read from `/data_limit/status`; the router counts
  and enforces the limit, the integration only shows it. The SIM slot comes
  from the interface configuration.
- **Port forward switches.** One switch per rule of `/firewall/port_forwards/config`
  that turns the rule on or off. Only the `enabled` field is written, and the
  setting is read back after the change like the roaming switches.
- The three pages are optional: a router or user without them gets no
  entities for them and everything else keeps working. They show up in the
  debug report and the diagnostics.
- The sample dashboard has a failover pill for mobile data, a port
  forward pill and a data limit pill. They hide themselves while their
  entities do not exist.
- The probe tool also reads `/data_limit/status` and the monthly data usage
  pages.

### Changed

- The failover state and the data limit are read at most every two minutes,
  like the DHCP clients, to keep the load on weak routers small. The port
  forward rules are configuration and follow the configuration interval.
- Docs: the router user needs read access to the new pages; the port forward
  switches are listed under what the integration changes on the router.

## [0.9.1] - 2026-11-16

### Fixed

- The debug log and the diagnostics download no longer show MAC or IP
  addresses that appear as key names in router answers. The Wi-Fi status of a
  radio lists its connected devices keyed by MAC address, and the structure
  view printed those keys. Such keys now show as `<mac>` or `<ip>` (one entry
  for the structure). The probe tool has the same protection. A test with a
  MAC address in the router data checks this.

## [0.9.0] - 2026-11-16

### Added

- **Debug logging for support.** With "Enable debug logging" on the
  integration page, the log now shows a router report (model, firmware, which
  pages answered, are missing or slow, counts of what was found), one line per
  request (method, path, HTTP status, duration, and for changes the names of
  the fields sent), the structure of each answer once per page (key names and
  types), one summary line per update and the actions that were run. It
  contains no passwords, tokens, PINs, IMSI/IMEI/ICCID, serial numbers, Wi-Fi
  names, addresses or coordinates; a test checks this.
- The diagnostics download lists which router pages work, are missing or are
  slow, and the structure of each answer.
- GitHub issue template that asks for the router model, firmware, debug log
  and diagnostics.

### Changed

- Connection errors without a text (timeouts) now say what happened, for
  example "Cannot reach 192.168.1.1: TimeoutError".
- Home Assistant no longer writes the router address into its own log lines of
  this integration (the update coordinator name used it).

### Changed

- Docs: the data roaming switches are confirmed on a RUTC50 in both
  directions (deny and allow); the router showed the new setting each time.

## [0.8.0] - 2026-11-16

### Added

- **Allow data roaming** switch for each SIM. It shows and changes the router
  setting "Deny data roaming" (on means roaming is allowed). Only this one
  field is written, never PIN or APN, the setting is read back after the
  change and an error is shown if the router did not apply it. The switches
  appear when the router answers the SIM settings page (`/sim_cards/config`).
- The sample dashboard has two pills for the roaming of SIM 1 and SIM 2:
  green when allowed, grey when denied. Allowing asks for confirmation.
- Configuration page `/sim_cards/config` is read with the other rarely
  changing pages.

### Notes

- The write request follows the pattern of the other settings but has not been
  tested on a real router yet. Try it first by turning the switch on while it
  is already on, which sends the value it already has.

## [0.7.0] - 2026-11-16

### Added

- Modem sensor **Network registration** (for example "Registered, home") and
  binary sensor **Roaming**, on while the registration says roaming. Both
  come from the modem status that is already read, so there is no new request
  to the router and no change on it.
- The sample dashboard has a **Network registration** pill that turns orange
  while roaming.
- `tools/probe_endpoints.py` also reads the modem configuration pages (used
  to look for the roaming setting).

### Changed

- Docs checked against the code and corrected: options list, password rule
  for secured networks (at least 8 characters), the Wi-Fi connected sensor,
  the GPS confirmation wording, the placeholder for the WireGuard instance in
  the sample dashboard and the order of the dashboard prerequisites.
- Docs: GPS heading and fix status checked on a RUTC50 (parked): both fields
  exist, the fix status is `1` with a fix, the heading is 0 when parked.
  Driving values are still to be confirmed.
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
