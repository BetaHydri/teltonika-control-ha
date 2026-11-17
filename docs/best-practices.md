# Best practices

Short rules that keep your router safe and your Home Assistant setup tidy.
Each rule links to the place in the documentation that explains it.

## Router access

- **Use a dedicated router user** for Home Assistant, not `admin`. Start with
  read rights only and add write rights for the pages you need. See
  [Router User and Permissions](../README.md#router-user-and-permissions).
- **Do not open the router web interface to the internet** for Home Assistant.
  Reach it over the LAN or a VPN.
- **Leave SSH off** for the Home Assistant user. The integration does not use
  it.

## Firewall switches

- **Switch a port forward or traffic rule on only while you need it**, for
  example the HTTP forward for a certificate renewal. A rule that is on lets
  traffic from the internet reach your router or a device behind it.
- **Never switch off the rule that carries your own remote access.** If you
  reach Home Assistant through a forwarded port, switching that rule off locks
  you out. Check the port before you tap.
- **Watch the counters** *Open port forwards* and *Firewall rules open to the
  internet*, or use the [firewall dashboard](firewall-dashboard.md), to see what
  is open right now.
- **Let the router create the rules.** The integration only turns existing
  rules on or off; create them once in the router web interface and leave them
  switched off by default.

## Uplink and hotspots

- **Save every Wi-Fi you use as a client network** on the router. Without one
  the priority select is unavailable.
- **Use *Wi-Fi first* only with a fallback**: an automation that returns to
  mobile data when the internet check fails, see
  [Automation examples](../README.md#automation-examples).
- **Set the internet check URL** (default answers HTTP 204). The hotspot
  login detection and the fallback depend on it. The check is only meaningful
  when Home Assistant reaches the internet through this router.
- **Expect a short break** when you change the SIM or restart the mobile
  connection. Do it from an automation only with a condition that tells it is
  safe.

## Mobile data

- **Keep the router data limit enabled.** It does the counting. Set it at or
  above your contract, because the router cuts mobile data at the limit unless
  its rate limit is on.
- **Enter your contract volume as *Mobile data plan (GB)*** in the options. The
  percentage and the warnings then follow your contract, not the router limit.
  See [Mobile data limit](../README.md#mobile-data-limit).
- **Warn from Home Assistant**, at 80 % and 95 % for example, instead of
  relying on the router's SMS. The README has a ready automation.
- **Mind the units**: the router counts in MB of 1,048,576 bytes, Home
  Assistant shows GB of 10⁹ bytes. Providers use the second.

## Automations

- **Use the entities, not the router API.** Everything is an entity of the
  router device; no helpers, scripts or YAML packages are needed.
- **Prefer native triggers**: `state` with `for:` for outages (hotspot login,
  Wi-Fi lost, VPN down), `numeric_state` for thresholds. A `for:` of two to
  three minutes avoids false alarms while the router reconnects.
- **Ignore `unknown` and `unavailable`** in change triggers, so a router
  reboot or a Home Assistant restart sends no notification.
- **Use a notification `tag`** and clear the message when the problem is gone,
  so old alerts do not pile up.
- **Choose the automation mode on purpose**: `restart` for timeouts,
  `queued` for messages that must all arrive, `single` for one-shots.
- **Use `entity_id`, never `device_id`**, so a re-added router does not break
  your automations.

## Performance

- **Keep the default intervals** (30 s status, 300 s configuration). A RUTC50
  has a weak CPU. If the router feels slow, raise both and watch the
  **CPU load** sensor. See [Options](../README.md#options).
- **Do not run other tools that poll the router at the same time**, such as a
  second integration or a script with its own login, if you see sign-in errors.
  RutOS can block an address after repeated failed logins.

## Dashboards

- **Replace the placeholder** in the sample dashboards with your entity prefix
  and check the result before you save.
- **Hide private data** (map, phone number, forwarded ports) before you share a
  screenshot.
- **Start from the sample, then trim.** Remove pills for hardware you do not
  have, such as a second SIM or Wi-Fi.

## When something is wrong

- Turn on [debug logging](../README.md#debug-logging) and download the
  diagnostics. Both redact the password.
- Check [Known Limitations](../README.md#known-limitations) first. Field names
  differ slightly between RutOS releases, so an empty entity is often worth an
  issue with the diagnostics attached.
