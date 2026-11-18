# Automation examples

Ready-made automations for Teltonika Control. Replace `my_router` with the
entity prefix of your router (see **Settings, Devices & services, Teltonika
Control, Entities**; in another language the endings differ) and the notify
service with your own. Services take any entity of the router as target.

The rules behind them are on the [best practices](best-practices.md) page.

- [Mobile data volume warning](#mobile-data-volume-warning)
- [Hotspot needs a login](#hotspot-needs-a-login)
- [Wi-Fi lost](#wi-fi-lost)
- [Uplink changed](#uplink-changed)
- [Back to mobile data when the Wi-Fi has no internet](#back-to-mobile-data-when-the-wi-fi-has-no-internet)
- [VPN to home is down](#vpn-to-home-is-down)
- [Restart the WireGuard tunnel](#restart-the-wireguard-tunnel)
- [Forward a new SMS](#forward-a-new-sms)
- [Send an SMS when the data volume runs low](#send-an-sms-when-the-data-volume-runs-low)
- [Move the home zone with the camper](#move-the-home-zone-with-the-camper)

## Mobile data volume warning

Needs the option **Mobile data plan (GB)**, see
[Mobile data limit](../README.md#mobile-data-limit). With the plan set, the
percentage is the share of your contract, so you can warn yourself at any point
without the router's SMS warning and without a helper. This notifies you at 80
and at 95 percent and names the volume that is left:

```yaml
alias: Mobile data volume warning
mode: queued
triggers:
  - trigger: numeric_state
    entity_id: sensor.my_router_data_limit_used_sim_1
    above: 80
    id: "80"
  - trigger: numeric_state
    entity_id: sensor.my_router_data_limit_used_sim_1
    above: 95
    id: "95"
conditions:
  - condition: template
    value_template: >-
      {{ trigger.from_state is not none
         and trigger.from_state.state not in ['unknown', 'unavailable'] }}
actions:
  - action: notify.notify
    data:
      title: "Mobile data: {{ trigger.id }} percent used"
      message: >-
        {{ states('sensor.my_router_data_used_sim_1') | float(0) | round(1) }} GB
        of {{ states('sensor.my_router_data_limit_sim_1') | float(0) | round(1) }} GB
        used. The counter resets on
        {{ as_timestamp(states('sensor.my_router_data_limit_reset_sim_1'), 0)
           | timestamp_custom('%d.%m.', true) }}.
```

A numeric state trigger fires once when the value crosses the threshold, and
fires again in the next month after the router has reset its counter. The
condition keeps it quiet after a restart of Home Assistant: the sensor then
changes from `unknown` to its real value, which would otherwise count as a
crossing and send the warning again. The router's data limit only has to be
enabled so that it keeps the count; the warning does not depend on its SMS
warning or on its cut-off.

## Hotspot needs a login

See [Hotspots With a Login Page](../README.md#hotspots-with-a-login-page). This
notifies you when the Wi-Fi is connected but has no internet for three minutes:

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

## Wi-Fi lost

The same pattern with the Wi-Fi connection. The trigger only fires on a real
change from `on` to `off`, so a Home Assistant restart sends nothing:

```yaml
automation:
  - alias: "Router: Wi-Fi lost"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_wifi_connected
        from: "on"
        to: "off"
        for: "00:02:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: Wi-Fi lost
          message: "Uplink: {{ states('sensor.my_router_uplink') }}"
```

## Uplink changed

Tells you each change, for example from Wi-Fi to mobile data, and ignores the
router restarting:

```yaml
automation:
  - alias: "Router: uplink changed"
    mode: queued
    triggers:
      - trigger: state
        entity_id: sensor.my_router_uplink
        not_from:
          - unknown
          - unavailable
        not_to:
          - unknown
          - unavailable
    actions:
      - action: notify.mobile_app_my_phone
        data:
          message: "{{ trigger.from_state.state }} → {{ trigger.to_state.state }}"
```

## Back to mobile data when the Wi-Fi has no internet

```yaml
automation:
  - alias: "Router: mobile first when the Wi-Fi is dead"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_internet
        to: "off"
        for: "00:02:00"
    conditions:
      - condition: state
        entity_id: sensor.my_router_uplink
        state: wifi
    actions:
      - action: teltonika_control.set_priority
        target:
          entity_id: sensor.my_router_uplink
        data:
          wifi_first: false
          verify: false
```

## VPN to home is down

Warns when the tunnel is down for five minutes while the router is online. See
[VPN check](../README.md#vpn-check).

```yaml
automation:
  - alias: "Router: VPN to home is down"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_vpn_reachable
        to: "off"
        for: "00:05:00"
    conditions:
      - condition: state
        entity_id: binary_sensor.my_router_internet
        state: "on"
    actions:
      - action: notify.notify
        data:
          message: "The VPN tunnel to home is down although the router is online."
```

## Restart the WireGuard tunnel

Restarts the tunnel when the VPN check has been failing for five minutes while
the router has internet. See [WireGuard tunnels](../README.md#wireguard-tunnels).

```yaml
automation:
  - alias: "Router: restart the WireGuard tunnel to home"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_vpn_reachable
        to: "off"
        for: "00:05:00"
    conditions:
      - condition: state
        entity_id: binary_sensor.my_router_internet
        state: "on"
      - condition: state
        entity_id: switch.my_router_wireguard_homebase_enabled
        state: "on"
    actions:
      - action: button.press
        target:
          entity_id: button.my_router_reconnect_wireguard_homebase
      - delay: "00:02:00"
```

The delay keeps the automation from restarting the tunnel again right away,
because the default mode `single` ignores new triggers while it runs.

## Forward a new SMS

Every new SMS on the router fires the event `teltonika_control_sms_received`, see
[SMS](../README.md#sms). This forwards it to your phone with the sender in the
title. Messages that were already on the router at startup are not announced.

```yaml
automation:
  - alias: "Router: forward a new SMS"
    mode: queued
    triggers:
      - trigger: event
        event_type: teltonika_control_sms_received
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "SMS from {{ trigger.event.data.sender }}"
          message: "{{ trigger.event.data.message }}"
```

To react only to one sender, add `event_data: {sender: "+491701111111"}` to the
trigger.

## Send an SMS when the data volume runs low

Sends an SMS to a number of your choice when the volume of your plan reaches 90
percent, for example to a second phone, when nobody sees the notification in
the app. Needs the option **Mobile data plan (GB)**, see
[Mobile data limit](../README.md#mobile-data-limit). Sending costs what an SMS
costs on the SIM.

```yaml
automation:
  - alias: "Router: SMS at 90 percent of the data volume"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.my_router_data_limit_used_sim_1
        above: 90
    conditions:
      - condition: template
        value_template: >-
          {{ trigger.from_state is not none
             and trigger.from_state.state not in ['unknown', 'unavailable'] }}
    actions:
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "+491701234567"
          message: >-
            Mobile data: {{ states('sensor.my_router_data_limit_used_sim_1') }} percent
            of the plan used.
```

## Move the home zone with the camper

When the router has been standing still for ten minutes, the Home Assistant
home location follows its GPS position.

```yaml
automation:
  - alias: "Camper: home zone follows the router when parked"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.my_router_gps_speed
        below: 1
        for: "00:10:00"
    conditions:
      - condition: template
        value_template: >-
          {{ state_attr('device_tracker.my_router_position', 'latitude') is number }}
    actions:
      - action: homeassistant.set_location
        data:
          latitude: "{{ state_attr('device_tracker.my_router_position', 'latitude') }}"
          longitude: "{{ state_attr('device_tracker.my_router_position', 'longitude') }}"
```
