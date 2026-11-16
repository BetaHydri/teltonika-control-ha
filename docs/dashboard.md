# Dashboard for Teltonika Control

A ready-made dashboard for your router. It shows the active uplink, the
Wi-Fi and mobile data state, and gives you buttons for the actions you need
on the road: Wi-Fi first or mobile first, hotspot login, restarting the
mobile connection, switching the SIM and switching the router's own Wi-Fi.

The dashboard uses only Home Assistant core cards. You do not need HACS
frontend cards.

The file is [dashboards/teltonika-control.yaml](../dashboards/teltonika-control.yaml).

## What you need

- Teltonika Control installed and set up, see the
  [getting started guide](getting-started.md).
- A version of the integration that accepts a service target (release 0.2.0
  or newer). The buttons call services with
  an entity of your router as target, so no device ID is needed.
- Home Assistant 2024.8 or newer for the `perform-action` button setting.

## Step 1: List your entity IDs

Entity IDs are created from the device name, the entity name and the area.
They differ between installations and between languages, so the dashboard
file contains placeholders. Get your real IDs first:

1. Go to **Developer tools**, **Template**.
2. Paste the template below. It lists every entity of the integration.

```jinja
{% for e in integration_entities('teltonika_control') | sort %}
{{ e }}  -  {{ state_attr(e, 'friendly_name') }}
{% endfor %}
```

Keep the result open, you need it in the next step. Disabled entities are not
listed. The dashboard does not use any of them.

## Step 2: Adjust the placeholders

The file uses two placeholders in all entity IDs:

| Placeholder | Replace with | Example |
|---|---|---|
| `my_router` | the part of your router entity IDs before the entity name | `rutc50_lan` |
| `my_modem` | the same for the modem entities | `internal_modem` |

For the entity `sensor.my_router_uplink` your list shows, for example,
`sensor.rutc50_lan_uplink`, so `my_router` becomes `rutc50_lan`. If you put
the router into an area, the area is part of the prefix, for example
`it_equipment_rutc50_lan`.

Use find and replace in a text editor on a copy of the file:

1. Replace `my_router` with your router prefix.
2. Replace `my_modem` with your modem prefix.
3. Replace `my_wifi` in the two switch entities with the name of your
   router's own Wi-Fi, as it appears in your list.

If Home Assistant runs in another language than English, the ending of each
entity ID is in that language too (for example `uplink_ip_adresse` in
German). Compare each ID in the file with your list and fix the ones that
differ. These are the entities the dashboard uses:

| Name in the English interface | Placeholder ID in the file |
|---|---|
| Uplink | `sensor.my_router_uplink` |
| Uplink IP address | `sensor.my_router_uplink_ip_address` |
| Wi-Fi network | `sensor.my_router_wi_fi_network` |
| Wi-Fi signal | `sensor.my_router_wi_fi_signal` |
| Wi-Fi band | `sensor.my_router_wi_fi_band` |
| Wi-Fi link speed | `sensor.my_router_wi_fi_link_speed` |
| Hotspot login | `sensor.my_router_hotspot_login` |
| Internet | `binary_sensor.my_router_internet` |
| Uplink priority | `select.my_router_uplink_priority` |
| Reconnect Wi-Fi | `button.my_router_reconnect_wi_fi` |
| Reboot router | `button.my_router_reboot_router` |
| Access point (one per Wi-Fi band) | `switch.my_router_access_point_my_wifi_2_4_ghz` |
| Operator | `sensor.my_modem_operator` |
| Network type | `sensor.my_modem_network_type` |
| Band | `sensor.my_modem_band` |
| RSRP, RSRQ, SINR | `sensor.my_modem_rsrp`, `_rsrq`, `_sinr` |
| Temperature | `sensor.my_modem_temperature` |
| Data received, Data sent | `sensor.my_modem_data_received`, `_data_sent` |
| Mobile data connected | `binary_sensor.my_modem_mobile_data_connected` |
| Restart mobile connection | `button.my_modem_restart_mobile_connection` |
| SIM slot | `select.my_modem_sim_slot` |

A router without a second SIM has no **SIM slot** select, and a router
without Wi-Fi has no Wi-Fi entities. Delete the cards for entities you do
not have.

## Step 3: Create the dashboard

1. Go to **Settings**, **Dashboards**, **Add dashboard**.
2. Choose **New dashboard from scratch**, give it a name such as
   `Teltonika Control` and create it.
3. Open the new dashboard, select the pencil (edit), then the three dots and
   **Raw configuration editor**.
4. Replace the content with your adjusted file and save.

If a card shows "Entity not found", the ID in the file does not match your
list. Fix that entity and save again.

## What the cards do

- **Connection**: the active uplink is green for Wi-Fi, orange for mobile
  data and red for anything else. The Wi-Fi card turns orange when the Wi-Fi
  has no internet (a hotspot login page) and red when the Wi-Fi is gone.
  **Wi-Fi first** and **Mobile first** call `teltonika_control.set_priority`.
  With Wi-Fi first, the integration goes back to mobile data when the Wi-Fi
  has no internet after 25 seconds.
- **Router control**: restart the mobile connection, reconnect the Wi-Fi and
  reboot the router. The hotspot button changes with the state: it starts
  `teltonika_control.portal_mode`, shows that it waits, and reports when
  the Wi-Fi has internet. See
  [hotspots with a login page](../README.md#hotspots-with-a-login-page).
- **Mobile data**: operator, network type, signal values, the active SIM with
  SIM 1 and SIM 2 buttons, modem temperature and the data counters.
- **Router's own Wi-Fi**: switches for the access points of the router.

Every action that interrupts the connection asks for confirmation first.

## What is not included

Scanning, adding and removing Wi-Fi networks, GPS and a monthly data limit
are not part of this dashboard. Scanning and managing networks are available
as actions, see the
[getting started guide](getting-started.md#step-9-everyday-tasks).

## See also

- [Getting started guide](getting-started.md)
- [README](../README.md)
