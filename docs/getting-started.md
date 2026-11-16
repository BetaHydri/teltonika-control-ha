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

| You want | Give the group |
|---|---|
| Only sensors | Read on the pages in the table below |
| Sensors and all controls | Read and write on the pages in the table below |

| Used for | Router page | Needs |
|---|---|---|
| Model and firmware | System, Device, Info | Read |
| Uplink and priority state | Network, Interfaces | Read |
| Change uplink priority | Network, Interfaces | Write |
| Wi-Fi and access point state | Network, Wireless, SSIDs | Read |
| Access point switches, reconnect, scan, add and remove networks | Network, Wireless, SSIDs | Write |
| Modem sensors | Network, Mobile | Read |
| Uptime, load, memory, DHCP clients, WireGuard state | Status pages, Network, Interfaces | Read |
| WireGuard switch and reconnect | Services, VPN, WireGuard | Read and write |
| Restart mobile connection, switch SIM | Network, Mobile, Modems | Write |
| Reboot the router | System, Administration, General | Write |

Menu names can differ slightly between RutOS releases. Teltonika does not
publish the exact permission entry for each action, so this table maps the
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

### With HACS

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/BetaHydri/teltonika-control-ha` with the type
   **Integration**.
3. Find **Teltonika Control**, install it and restart Home Assistant.

### Manually

Copy the folder `custom_components/teltonika_control` into the
`custom_components` folder of your Home Assistant configuration, then
restart Home Assistant.

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

- Sensors for the uplink (Wi-Fi, mobile, Ethernet or other), its IP address
  and, if the router is a Wi-Fi client, the network name, signal, band and
  link speed.
- Binary sensors for Wi-Fi connected, internet and hotspot login required.
- One switch for each access point of the router.
- The **Uplink priority** select, the **Reconnect Wi-Fi** and **Reboot
  router** buttons.
- To manage Wi-Fi networks: the buttons **Scan for Wi-Fi networks**,
  **Add selected network** and **Remove selected network**, the selects
  **Found networks** and **Saved networks**, the **Wi-Fi password** field and
  the **Last Wi-Fi action** sensor.
- On routers with GPS: the **Position** device tracker and sensors for speed,
  altitude, satellites and accuracy.
- If you set a VPN check host ([step 12](#step-12-optional-vpn-check)): the
  binary sensor **VPN reachable** and the sensor **VPN latency**.
- Router health sensors: **Uptime**, **CPU load**, **Memory usage** and
  **DHCP clients**.
- For every WireGuard instance on the router
  ([step 13](#step-13-optional-restart-a-wireguard-tunnel)): a binary sensor,
  a switch, a **Reconnect WireGuard** button and traffic counters.

Select the modem device to see operator, network type, network registration,
signal values (RSRP, RSRQ, SINR), temperature, SIM state and data counters,
the **Roaming** binary sensor, the
**Restart mobile connection** button and, on dual SIM modems, the
**SIM slot** select.

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
radio is already used, the button tells you which network occupies it.
On a radio that runs in Multi AP mode (the 5 GHz radio of the RUTC50), the
network is added to the Multi AP list instead. See
[Multi AP radios](../README.md#multi-ap-radios) for details.

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

Some campsite and hotel Wi-Fi networks need a click on a landing page.

1. Call `teltonika_control.portal_mode`. Wi-Fi gets priority and the
   integration waits.
2. On a phone connected to the router, open `http://neverssl.com` and accept
   the hotspot page.
3. When the internet check passes, the router stays on Wi-Fi and the event
   `teltonika_control_portal_result` fires with `success: true`. If there is
   no internet within the wait time, the router returns to mobile data.

The **Hotspot login** sensor shows `login_required` while Wi-Fi is the uplink
but has no internet. The README has an
[example notification](../README.md#notification-example) for it.

### Restart the mobile connection or switch the SIM

Press **Restart mobile connection** on the modem device. On dual SIM
modems, use the **SIM slot** select. Switching the SIM drops mobile data for
about a minute.

## Step 10: Adjust the options

Go to **Settings**, **Devices & services**, **Teltonika Control**, then
select **Configure**.

- **Update interval**: how often the status of the router is polled (uplink,
  Wi-Fi signal, modem, GPS, load), 10 to 600 seconds. The default is 30
  seconds.
- **Configuration interval**: how often the pages that rarely change are read
  again (Wi-Fi configuration, radios, WireGuard instances), 30 to 3600
  seconds. The default is 300 seconds. Actions of the integration, such as
  switching the priority or adding a network, read them again at once. A
  RUTC50 has a weak CPU: if the router feels slow, raise both values.
- **Internet check URL**: a web address that answers with HTTP 204 when the
  internet works. It is used to detect a hotspot login page. Leave it empty
  to turn the check off.
- **VPN check host**: optional. A DNS name, IPv4 or IPv6 address of a device
  behind your VPN tunnel, for example the router at your home base
  (`192.168.178.1`). With it, the sensors **VPN reachable** and **VPN
  latency** appear. Leave it empty to turn the check off. Details and
  limits are in the [README](../README.md#vpn-check).
- **VPN check port**: the TCP port for that check, default 443. A refused
  connection also counts as reachable.

The internet check runs on the Home Assistant host, so it only says
something about the router if Home Assistant reaches the internet through
this router.

## Step 11: Optional helpers for a monthly data counter

This step is optional. The integration has no monthly counter of its own,
but the modem's **Received** and **Sent** sensors count upwards, so a
built-in Utility Meter helper can turn them into monthly values. Do this once
for each of the two sensors:

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
needed. The router only has to route to the remote network, which the VPN
already does.

1. Choose a device at the other end of the tunnel that is always on, for
   example the home router (`192.168.178.1`). Use an address inside the
   tunnel's network, or a DNS name that resolves to it. Do not use the
   WireGuard endpoint from the peer settings (public name and UDP port): it
   never answers TCP and is not reached through the tunnel.
2. Check from a device on the router's LAN that you can reach it, for example
   by opening its web page or by running `ping` in a terminal.
3. Go to **Settings**, **Devices & services**, **Teltonika Control**, select
   **Configure**.
4. Enter the address in **VPN check host**. IPv4, IPv6 and DNS names work. You
   can add the port behind it, for example `192.168.178.1:443` or
   `[fd00::1]:443`.
5. Set **VPN check port** to a port the device answers or rejects. The default
   is 443. A refused connection counts as reachable, a silent timeout counts as
   down.
6. Select **Submit**. The integration reloads.
7. On the router device you now see **VPN reachable** (binary sensor) and
   **VPN latency** (sensor, diagnostic). If you use the sample dashboard, the
   VPN pill appears in the Connection section.

To turn the check off, empty the **VPN check host** field again. The two
entities then remain in the entity list as unavailable until you delete them.

What the check does and does not tell you is described in the
[README](../README.md#vpn-check). In short: it tests the whole path through
the tunnel from the Home Assistant host, but it does not show the WireGuard
handshake. To restart a WireGuard tunnel, see
[WireGuard tunnels](../README.md#wireguard-tunnels).

## Step 13: Optional: restart a WireGuard tunnel

This step is optional and needs a WireGuard instance on the router (**Services**,
**VPN**, **WireGuard**). No extra setup in Home Assistant is needed: the
entities appear by themselves for every instance.

1. Make sure the router user of step 2 may read and change the WireGuard
   configuration (**Services**, **VPN**, **WireGuard**, read and write). Without
   the right to change it, you still get the interface state and the traffic
   counters, but no switch and no button.
2. Open the router device in Home Assistant. For an instance named `HOMEBASE`
   you see **WireGuard HOMEBASE** (binary sensor), **WireGuard HOMEBASE
   enabled** (switch), **Reconnect WireGuard HOMEBASE** (button) and the
   counters **received** and **sent**.
3. Press **Reconnect WireGuard HOMEBASE** to test it. The router switches the
   instance off, waits a few seconds and switches it on again. Traffic through
   the tunnel is interrupted for that time. Do not test it while you are
   connected to the router through that tunnel.
4. To restart the tunnel automatically when the [VPN check](#step-12-optional-vpn-check)
   fails, use the automation in the
   [README](../README.md#wireguard-tunnels).

If the tunnel is switched off, the button refuses. Use the switch to turn it
on. The tunnel entities show nothing about the last handshake, because the
router does not offer it through its API. The binary sensor tells you that
the interface is up, and the VPN check tells you whether the other end
answers.

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
| Some values do not update and the log says "The router did not answer for ... in time" | One page of the router (often the Wi-Fi status) is slow or stuck. The integration keeps the last known values for that page, asks again after two minutes and keeps all other entities working. If it does not recover, restart the router's Wi-Fi or reboot the router. |
| Values look wrong or an entity stays empty | Field names differ slightly between RutOS releases. Download the diagnostics and open an issue. |

### Download diagnostics

Go to **Settings**, **Devices & services**, **Teltonika Control**, open the
menu (three dots) of the entry and choose **Download diagnostics**. The file
has the password and other personal data removed. Attach it to an issue.

### Turn on debug logging

Add this to `configuration.yaml`, restart Home Assistant and reproduce the
problem. Remove it again afterwards.

```yaml
logger:
  logs:
    custom_components.teltonika_control: debug
```

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
