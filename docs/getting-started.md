# Getting started with Teltonika Control

This guide takes you from a Teltonika RUTC or RUTX router to working
controls in Home Assistant, one step at a time. It is written for Home
Assistant users who are not router experts. Plan about 15 minutes.

When you are done you can see which uplink the router uses, switch between
Wi-Fi and mobile data, restart the mobile connection, add Wi-Fi networks and
get notified when a hotspot needs a login, all from Home Assistant.

## What you need

- A Teltonika RUTC or RUTX router with **RutOS 7**.
- Home Assistant 2025.2 or newer. It must be able to reach the router over
  the network.
- The router address, for example `192.168.1.1`, and an administrator login
  for the one-time user setup.
- Optional: [HACS](https://hacs.xyz/) for easy installation and updates.
- Optional: a device behind your VPN tunnel to check, see
  [step 12](#step-12-optional-vpn-check).

The integration only polls the router. The router never connects to Home
Assistant and no cloud account is needed.

**No Home Assistant helpers are required.** The integration does not use
`input_*` helpers, timers, counters, scripts, template sensors or YAML
packages. Everything, including adding and removing Wi-Fi networks, is an
entity of the router device. Helpers are only needed for the optional
extras in [step 11](#step-11-optional-helpers-for-a-monthly-data-counter),
and the sample dashboard needs frontend cards, see the
[dashboard guide](dashboard.md).

## Step 1: Find the router address

Use the address you open in the browser to reach the router web interface.
It is usually `192.168.1.1`. Make a note of it. If Home Assistant is not in
the router's own network, make sure it can still open that address, and
allow the access in the router (see step 3).

## Step 2: Create a user for Home Assistant

Do not use `admin` for Home Assistant. A dedicated user keeps the rights
small and lets you change or remove the access later without touching your
own login.

1. Open the router web interface and sign in as administrator.
2. Go to **System**, **Administration**, **User Settings**.
3. Create a group for Home Assistant, or pick an existing one, and give it
   the rights from the table below.
4. Create a user in that group with a strong, unique password. Leave SSH
   access off for this user.
5. Write down the user name and password. You enter them in Home Assistant
   in step 5.

Start with **read** rights, or give **read and write** for all controls. Which
router page each function needs is listed in
[Router User and Permissions](../README.md#router-user-and-permissions).

Menu names can differ slightly between RutOS releases. Teltonika does not
publish the exact permission entry for each action, so the list maps the
actions to the router pages they belong to. If Home Assistant later shows an
error when you press a control, the message comes from the router: give the
group read or write on the matching page and try again.

## Step 3: Allow access from Home Assistant

Skip this step if Home Assistant is on the router's own network (LAN).

If Home Assistant reaches the router from another network, allow the web
interface for that network under **System**, **Administration**, **Access
Control**, **General** and in the router firewall. Do not open the router
web interface to the internet. Use your LAN or a VPN instead.

## Step 4: Test the login from the Home Assistant side

This optional check saves time when something is wrong. It proves that the
address, the HTTPS port and the login work, before you touch Home Assistant.

On the Home Assistant host (for example in the Terminal add-on), run the
commands below in a bash shell. They ask for the user and password so that
the password does not end up in your shell history, and print only whether
the login worked.

```bash
read -p "Router user: " U
read -s -p "Router password: " P; echo
curl -sk -X POST https://192.168.1.1/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$U\",\"password\":\"$P\"}" \
  | grep -o '"success":[a-z]*'
unset U P
```

Replace `192.168.1.1` with your router address. `"success":true` means you
are ready. `"success":false` points to the user name, the password or the
rights of the group. No output at all means the router cannot be reached;
check the address, the network and step 3.

## Step 5: Install the integration

With HACS, add `https://github.com/BetaHydri/teltonika-control-ha` as a custom
repository of the type **Integration** (menu **Custom repositories**), install
**Teltonika Control** and restart Home Assistant. Manually, copy the folder
`custom_components/teltonika_control` into the `custom_components` folder of
your Home Assistant configuration and restart.

## Step 6: Add the router

1. In Home Assistant, go to **Settings**, **Devices & services**.
2. Select **Add integration** and search for **Teltonika Control**.
3. Fill in the form:

   | Field | What to enter |
   |---|---|
   | Host | The router address, for example `192.168.1.1`. Put `http://` in front to use plain HTTP. |
   | Username | The user from step 2. |
   | Password | The password of that user. |
   | Verify SSL certificate | Leave **off** if the router uses its built-in self-signed certificate (the default). |

4. Select **Submit**.

Home Assistant creates one device for the router and one device for each
modem. If you see an error, go to [Troubleshooting](#troubleshooting).

## Step 7: Check what you got

Open **Settings**, **Devices & services**, **Teltonika Control** and select
the router device. You should see:

- Sensors for the uplink and, if the router is a Wi-Fi client, the network
  name, signal, band and link speed, plus the binary sensors Wi-Fi connected,
  internet and hotspot login required.
- The **Uplink priority** select, the **Reconnect Wi-Fi** and **Reboot
  router** buttons, one switch for each access point and the entities to
  manage Wi-Fi networks (scan, found networks, password, add, saved networks,
  remove, last action).
- Router health sensors: **Uptime**, **CPU load**, **Memory usage** and
  **DHCP clients**.
- Only where the router has it: the GPS **Position** and sensors, the VPN
  entities ([step 12](#step-12-optional-vpn-check) and
  [step 13](#step-13-optional-restart-a-wireguard-tunnel)), SMS, firmware,
  firewall switches and the data limit.

Select the modem device to see operator, network type, network registration,
signal values (RSRP, RSRQ, SINR), temperature, SIM state and data counters,
the **Roaming** binary sensor, the **Allow data roaming** switch of each SIM, the
**Restart mobile connection** button and, on dual SIM modems, the
**SIM slot** select. The complete list is in
[What You Get](../README.md#what-you-get).

Some entities only appear when the router can provide them. The priority
select needs at least one saved Wi-Fi client network (see step 9), and modem
entities need a modem with a SIM.

## Step 8: Build a first dashboard card

Entity IDs depend on the router name, the area you put it in and your
language, so the easiest way is to add the card in the dashboard editor and
pick the entities from the list. For example, a router named `RUTC50.lan` in
the area `IT-Equipment` with Home Assistant in English gets IDs such as
`sensor.it_equipment_rutc50_lan_uplink`; without an area it is
`sensor.rutc50_lan_uplink`.

As a starting point, switch the card editor to **Show code editor** and
paste the following. It assumes IDs that start with `rutc50_lan`. Replace
that part with the beginning of your own entity IDs.

```yaml
type: entities
title: Router
entities:
  - entity: sensor.rutc50_lan_uplink
  - entity: sensor.rutc50_lan_wi_fi_network
  - entity: sensor.rutc50_lan_wi_fi_signal
  - entity: binary_sensor.rutc50_lan_internet
  - entity: select.rutc50_lan_uplink_priority
  - entity: button.rutc50_lan_reconnect_wi_fi
  - entity: button.rutc50_lan_reboot_router
    name: Reboot router (careful)
```

Add the modem entities the same way from the modem device. Reboot and SIM
changes interrupt the connection, so it is wise to put them behind a
confirmation in your dashboard (a button card with a `confirmation` entry in
its tap action).

For a complete ready-made dashboard, see the
[dashboard guide](dashboard.md).

## Step 9: Everyday tasks

### Switch between Wi-Fi and mobile data

Use the **Uplink priority** select: **Wi-Fi first** or **Mobile first**. The
router needs at least one saved Wi-Fi client network. When you choose Wi-Fi
first, the integration reconnects the Wi-Fi so the change takes effect.

To go to Wi-Fi first and fall back to mobile data automatically if the
Wi-Fi has no internet, call the action `teltonika_control.set_priority`:

```yaml
action: teltonika_control.set_priority
target:
  entity_id: sensor.my_router_uplink
data:
  wifi_first: true
  verify: true
```

Use any entity of your router as target. Replace `sensor.my_router_uplink`
with the entity ID of the **Uplink** sensor from your list.

### Add a Wi-Fi network

Use the entities of the router device, for example on the
[dashboard](dashboard.md):

1. Press **Scan for Wi-Fi networks**. The scan takes a few seconds per radio.
2. Choose a network in **Found networks**. Each network appears once per
   band with its best signal, and networks you already saved are hidden.
3. Type the password into **Wi-Fi password** and press Enter. A secured
   network needs a password of at least 8 characters, leave it empty for open
   networks. Home Assistant only keeps the password in memory and shows
   `********` instead of the text. On the sample dashboard, the key button on
   the highlighted network opens this field.
4. Press **Add selected network**. Without a password for a secured network,
   Home Assistant tells you to enter one first.

**Last Wi-Fi action** tells you what happened, for example `Saved CampsiteWifi`.
Mobile data stays preferred until you switch to **Wi-Fi first**, so a new
network never breaks your connection by itself.

A router radio can hold only one Wi-Fi client or one Multi AP list. If a
radio is already used, the button tells you which network occupies it. On a
radio that runs in Multi AP mode (the 5 GHz radio of the RUTC50), the network is
added to the Multi AP list instead, see
[Multi AP radios](../README.md#multi-ap-radios).

The same is possible as actions, for automations or scripts. Run them in
**Developer tools**, **Actions**, with any entity of the router as target:

```yaml
action: teltonika_control.scan_wifi
target:
  entity_id: sensor.my_router_uplink
```

The response lists `ssid`, `signal`, `band`, `encrypted` and the `radio`
that found each network. Save one with the `radio` from the scan:

```yaml
action: teltonika_control.join_wifi
target:
  entity_id: sensor.my_router_uplink
data:
  radio: radio0
  ssid: CampsiteWifi
  password: "the Wi-Fi password"
```

### Connect to a saved Wi-Fi network

After arriving at a new place, choose the network in **Saved networks** and
press **Connect selected network**. The router then tries that network now
instead of waiting. A Wi-Fi client is reconnected. An entry of a Multi AP list
is moved to the top of the list first (the router tries the list by priority)
and the Multi AP radio reconnects.
**Last Wi-Fi action** shows `Connecting to ... ...`.

### Remove a Wi-Fi network

Choose the network in **Saved networks** and press **Remove selected
network**. The list shows Wi-Fi clients and the entries of a Multi AP list.
The last Multi AP entry cannot be removed through Home Assistant.

As an action:

```yaml
action: teltonika_control.forget_wifi
target:
  entity_id: sensor.my_router_uplink
data:
  station_id: "6"
```

Use `ssid` instead of `station_id` for networks in a Multi AP list.

### Use a hotspot that shows a login page

Call `teltonika_control.portal_mode`, open `http://neverssl.com` on a phone
connected to the router and accept the hotspot page. When the internet check
passes, the router stays on Wi-Fi. The steps and the **Hotspot login** sensor
are described in
[Hotspots With a Login Page](../README.md#hotspots-with-a-login-page), and
there is an [example notification](automation-examples.md#hotspot-needs-a-login)
for it.

### Restart the mobile connection or switch the SIM

Press **Restart mobile connection** on the modem device. On dual SIM
modems, use the **SIM slot** select. Switching the SIM drops mobile data for
about a minute. If the other slot holds no SIM, the integration notices it
(binary sensor **No SIM in the active slot**), switches back and shows an
error.

## Step 10: Adjust the options

Go to **Settings**, **Devices & services**, **Teltonika Control**, then
select **Configure**. The defaults suit most routers. What each option does is
described in [Options](../README.md#options): the two intervals (raise both if
a weak router such as the RUTC50 feels slow), the internet check URL, the VPN
check host and port, and the mobile data plan.

## Step 11: Optional helpers for a monthly data counter

This step is optional. If you set a **Data limit** on the router, the
integration already shows the used data and the percentage, see
[Mobile data limit](../README.md#mobile-data-limit). Without a limit, the
integration has no monthly counter of its own, but the modem's **Received** and
**Sent** sensors count upwards, so a built-in Utility Meter helper can turn them
into monthly values. Do this once for each of the two sensors:

1. Go to **Settings**, **Devices & services**, **Helpers**.
2. Select **Create helper**, then **Utility Meter**.
3. Enter a **Name**, for example `Mobile data received monthly`.
4. Select the modem sensor **Received** (or **Sent**) as **Input sensor**.
5. Set **Meter reset cycle** to **Monthly**. Leave the other options off.
6. Select **Submit**.

The new sensor starts at zero and resets at the start of each month. To get
the total traffic, add a **Sum** helper (**Create helper**, **Combine the
state of several sensors**) over the two meters. For a warning at a limit,
create an automation with a numeric state trigger on that sensor.

These helpers belong to you, not to the integration. Removing the integration
does not remove them.

## Step 12: Optional VPN check

This step is optional. Use it if the router carries a site-to-site VPN (for
example WireGuard, OpenVPN or IPsec) and you want to know in Home Assistant
whether the tunnel carries traffic. No helper and no extra router setting is
needed.

1. Choose a device at the other end of the tunnel that is always on, for
   example the home router (`192.168.178.1`), with an address inside the
   tunnel's network. Check from a device on the router's LAN that you can reach
   it, for example by opening its web page or by running `ping`.
2. Go to **Settings**, **Devices & services**, **Teltonika Control**, select
   **Configure**, enter the address in **VPN check host** and a port the device
   answers or rejects in **VPN check port**, and submit. The integration
   reloads.
3. On the router device you now see **VPN reachable** (binary sensor) and
   **VPN latency** (sensor, diagnostic). If you use the sample dashboard, the
   VPN pill appears in the Connection section.

Which address and port to choose, and what the check does and does not tell
you, is described in the [README](../README.md#vpn-check). To turn the check
off, empty the **VPN check host** field again. The two entities then remain in
the entity list as unavailable until you delete them.

## Step 13: Optional: restart a WireGuard tunnel

This step is optional and needs a WireGuard instance on the router (**Services**,
**VPN**, **WireGuard**). No extra setup in Home Assistant is needed: the
entities appear by themselves for every instance.

1. Make sure the router user of step 2 may read and change the WireGuard
   configuration. Without the right to change it, you still get the interface
   state and the traffic counters, but no switch and no button.
2. Open the router device in Home Assistant. For an instance named `HOMEBASE`
   you see **WireGuard HOMEBASE**, **WireGuard HOMEBASE enabled**, **Reconnect
   WireGuard HOMEBASE** and the traffic counters.
3. Press **Reconnect WireGuard HOMEBASE** to test it. The router switches the
   instance off, waits a few seconds and switches it on again. Traffic through
   the tunnel is interrupted for that time, so do not test it while you are
   connected to the router through that tunnel.

What the entities mean, why the button can refuse and how to restart the tunnel
automatically when the [VPN check](#step-12-optional-vpn-check) fails, is in
[WireGuard tunnels](../README.md#wireguard-tunnels).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| "Failed to connect" when adding the router | Home Assistant cannot reach the router. Check the address, run the test in step 4 and check step 3. If the router only offers HTTP, put `http://` before the host. |
| "Invalid authentication" | Wrong user name or password, or the user is not allowed to use the API. Check the user in step 2. After many wrong tries the router can block the address for a while; check **System**, **Administration**, **Access Control**, **Security**. |
| Home Assistant asks you to sign in again | The stored password was rejected, for example after you changed it on the router. Enter the new password in the dialog. |
| Router address changed | Use **Reconfigure** on the integration to enter the new address. |
| Some entities are missing | Modem entities need a modem with a SIM. The priority select needs a saved Wi-Fi client network. Wi-Fi sensors need Wi-Fi hardware. |
| A button or action fails with a message from the router | The user lacks a right. Give the group write access to the matching page (step 2). |
| `join_wifi` says a radio already has a client | The router allows one client or one Multi AP list per radio. Remove the existing one first, or use the other radio. |
| The Internet sensor is off although the router has internet | Home Assistant may not reach the internet through this router, or your network blocks the check URL. Change the URL in the options or empty it. |
| VPN reachable is off although the tunnel works | The device or port you chose does not answer. Pick an always-on device inside the tunnel's network and a port it answers or rejects (a firewall that silently drops the port looks like a dead tunnel). Do not use the WireGuard endpoint and its UDP port, TCP never reaches it. Check that Home Assistant itself reaches the remote network through this router. |
| VPN reachable is on although the tunnel looks dead | The name or address resolves to a device on the local network, or Home Assistant reaches the remote network by another route. Use an address that only exists behind the tunnel. |
| No uptime, CPU load, DHCP client or WireGuard entities | The router user may not read those pages (the router answers with an error), or the router has no WireGuard instance. Give the group read access, see step 2, and reload the integration. |
| A WireGuard tunnel has no switch and no reconnect button | The user may not read and change **Services**, **VPN**, **WireGuard**. Give the group read and write there and reload the integration. |
| **Reconnect WireGuard** says the tunnel is switched off | The reconnect button only works on a tunnel that is switched on. Turn the **WireGuard ... enabled** switch on instead. |
| **Allow data roaming** says the router did not apply the setting | The router did not take the change, or the user may not change the mobile settings. Check **Network**, **Mobile**, **General**, **SIM configuration** on the router, and give the group read and write on that page. |
| There is no **Allow data roaming** switch | The router did not answer the SIM settings page (the user may not read it), or the modem is offline. Give the group read access on **Network**, **Mobile**, **General** and reload the integration. |
| Some values do not update and the log says "The router did not answer for ... in time" | One page of the router (often the Wi-Fi status) is slow or stuck. The integration keeps the last known values for that page, asks again after two minutes and keeps all other entities working. If it does not recover, restart the router's Wi-Fi or reboot the router. |
| Values look wrong or an entity stays empty | Field names differ slightly between RutOS releases. Download the diagnostics and open an issue. |

### Download diagnostics

Go to **Settings**, **Devices & services**, **Teltonika Control**, open the
menu (three dots) of the entry and choose **Download diagnostics**. The file
has the password and other personal data removed. It also lists which pages
of the router answered, which are missing, and the structure of each answer
(key names and types, no values). Attach it to an issue.

### Turn on debug logging

The debug log explains what the integration asked the router, what came back
and what it decided. It is the best help if a feature does not work on your
router model.

1. Go to **Settings**, **Devices & services**, **Teltonika Control**.
2. Open the menu (three dots, top right) and choose **Enable debug logging**.
3. Reproduce the problem, for example press the button that does not work.
4. Open the same menu and choose **Disable debug logging**. Your browser
   downloads the log file.
5. Open the file, check it (see below) and attach it to an issue.

The same can be set in `configuration.yaml`, followed by a restart of Home
Assistant. Remove it again afterwards:

```yaml
logger:
  logs:
    custom_components.teltonika_control: debug
```

What to look for and what the log never contains is described in the
[README](../README.md#debug-logging).

## Update and remove

- **Update**: with HACS, install the new version and restart Home Assistant.
  With a manual installation, replace the folder and restart.
- **Remove**: go to **Settings**, **Devices & services**, **Teltonika
  Control**, open the menu of the entry and choose **Delete**. Afterwards,
  delete the router user from step 2 if you no longer need it.

## See also

- [README](../README.md) for the full list of entities and services.
- [Changelog](../CHANGELOG.md)
- [Teltonika API documentation](https://developers.teltonika-networks.com/)
