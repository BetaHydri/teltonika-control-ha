# Automation examples

**English** | [Deutsch](automation-examples.de.md)

Ready-made automations for Teltonika Control. Replace `my_router` with the
entity prefix of your router (see **Settings, Devices & services, Teltonika
Control, Entities**; in another language the endings differ) and the notify
service with your own. Services take any entity of the router as target.

The rules behind them are on the [best practices](best-practices.md) page.

- [Mobile data volume warning](#mobile-data-volume-warning)
- [Hotspot needs a login](#hotspot-needs-a-login)
- [Wi-Fi lost](#wi-fi-lost)
- [Uplink changed](#uplink-changed)
- [Somebody arrives in or leaves the camper](#somebody-arrives-in-or-leaves-the-camper)
- [Back to mobile data when the Wi-Fi has no internet](#back-to-mobile-data-when-the-wi-fi-has-no-internet)
- [VPN to home is down](#vpn-to-home-is-down)
- [Restart the WireGuard tunnel](#restart-the-wireguard-tunnel)
- [Forward a new SMS](#forward-a-new-sms)
- [Send an SMS from a button](#send-an-sms-from-a-button)
- [Send the typed SMS from a script](#send-the-typed-sms-from-a-script)
- [Commands by SMS](#commands-by-sms)
- [Send an SMS when the data volume runs low](#send-an-sms-when-the-data-volume-runs-low)
- [Send the position by SMS](#send-the-position-by-sms)
- [Alarm by SMS when the camper moves](#alarm-by-sms-when-the-camper-moves)
  ([with the presence trackers](#with-the-presence-trackers))
- [Daily status by SMS](#daily-status-by-sms)
- [Download new firmware at night](#download-new-firmware-at-night)
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

## Somebody arrives in or leaves the camper

With the phones chosen as [presence](../README.md#presence-who-is-on-the-wi-fi)
and added to the people, a person changes between `home` and `not_home` when the
phone joins or leaves the Wi-Fi of the router. In a Home Assistant that runs in
the camper, `home` means in the camper. This tells you when anybody arrives:

```yaml
automation:
  - alias: "Camper: somebody arrived"
    triggers:
      - trigger: state
        entity_id:
          - person.jan
          - person.xin
        from: not_home
        to: home
    actions:
      - action: notify.mobile_app_my_phone
        data:
          message: "{{ trigger.to_state.name }} is in the camper"
```

The trackers of the integration, `device_tracker.laptop_router` for example,
can also be used directly in a condition or a trigger.

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

## Send an SMS from a button

For a message you send often, such as "I arrived", a script with a fixed number
and text is easier than typing it. Run it from a dashboard button, a widget or
voice. Sending costs what an SMS costs on the SIM.

```yaml
script:
  sms_arrived:
    alias: "SMS: arrived"
    sequence:
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "+491701234567"
          message: "We arrived. The camper is parked."
```

In the dashboard, add a button card that runs `script.sms_arrived` and ask for a
confirmation (`tap_action` with `confirmation`).

## Send the typed SMS from a script

The entities **SMS number**, **SMS text** and **Send SMS** (see
[SMS](../README.md#sms)) can be used from a script too, for example to fill the
fields from a Companion app notification action or a helper, and send in one
step:

```yaml
script:
  sms_from_helpers:
    alias: "SMS: send the helper text"
    sequence:
      - action: text.set_value
        target:
          entity_id: text.my_router_sms_number
        data:
          value: "{{ states('input_text.sms_to') }}"
      - action: text.set_value
        target:
          entity_id: text.my_router_sms_text
        data:
          value: "{{ states('input_text.sms_body') }}"
      - action: button.press
        target:
          entity_id: button.my_router_send_sms
```

If the sending fails (no number, no text, the router refuses), the script stops
with the reason and the sensor **SMS send result** shows it as well. To send a
text that depends on a template, the service `send_sms` is shorter: it takes
number and message in one call and returns how many SMS parts it used.

## Commands by SMS

An SMS can trigger something at the camper when there is no internet, for
example "heating on". Because anybody who knows the number could send such an
SMS, **always check the sender** and keep the command harmless (the sender alone
is no proof, see the note below the example). This turns the
heating on and answers with an SMS to the sender:

```yaml
automation:
  - alias: "Router: SMS command heating on"
    mode: queued
    triggers:
      - trigger: event
        event_type: teltonika_control_sms_received
        event_data:
          sender: "+491701111111"
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.message | trim | lower == 'heating on' }}"
    actions:
      - action: climate.turn_on
        target:
          entity_id: climate.camper_heating
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "{{ trigger.event.data.sender }}"
          message: "Heating is on."
```

The router is asked every two minutes, so the command can take up to that long
to arrive. The sender is the number as the network reports it, usually with
the country code; check how it shows up in the event (Developer tools, Events,
listen to `teltonika_control_sms_received`) before you rely on the match.
Do not use commands that open locks or switch off alarms.

> [!NOTE]
> **This is not the router's "SMS Utilities".** The SMS Utilities of RutOS
> (Services, Mobile Utilities) only control the router itself, for example
> reboot, Wi-Fi, mobile data, VPN or I/O, and they cannot call Home Assistant.
> The integration does not use them: it reads the SMS inbox of the router and
> fires the event, and the automation above does the rest. You do not have to
> enable or configure any SMS Utilities rule for it.
>
> - **Do not reuse a rule keyword** of the router (`reboot`, `status`,
>   `mobileoff`, `wifion`, ...) as your command. If such a rule is enabled and
>   the text matches (for "No authorization" the bare keyword, otherwise the
>   keyword after the authorization key), the router executes it too.
> - **The sender number is no secret.** The number of an SMS can be forged. The
>   SMS Utilities protect their rules with a key in the text (admin password,
>   serial number or own password). Do the same for a command that matters: add
>   a secret word to the text and check it in the condition, for example
>   `value_template: "{{ trigger.event.data.message | trim == 'MySecret heating on' }}"`.
>   Keep the secret out of shared automations and screenshots.

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

## Download new firmware at night

When the router has found a newer firmware, this downloads it at night and tells
you when it is ready. It **does not install** anything: you decide when the
router restarts, see [Firmware update](../README.md#firmware-update). The
download takes some mobile data (the file is about 35 MB), so use it with a
data plan that allows that, or only while the Wi-Fi is the uplink.

```yaml
automation:
  - alias: "Router: download new firmware at night"
    mode: single
    triggers:
      - trigger: time
        at: "03:00:00"
    conditions:
      - condition: state
        entity_id: update.my_router_firmware
        state: "on"
      - condition: state
        entity_id: sensor.my_router_uplink
        state: wifi
    actions:
      - action: button.press
        target:
          entity_id: button.my_router_download_firmware
      - wait_for_trigger:
          - trigger: state
            entity_id: sensor.my_router_firmware_status
            to: ready
        timeout: "00:30:00"
        continue_on_timeout: false
      - action: notify.mobile_app_my_phone
        data:
          title: "Router firmware downloaded"
          message: >-
            Version {{ state_attr('update.my_router_firmware', 'latest_version') }}
            is ready. Install it when you can be offline for ten minutes.
```

The automation presses only the download button. Do not press **Install
firmware** from an automation unless you are sure the router can be offline.

## Send the position by SMS

A script that sends the position of the router as a Google Maps link, for a
button, a voice command or another automation. The link opens in the map app
of the receiving phone. The position comes from the **Position** tracker of the
router (see [GPS](../README.md#gps)); without a fix the router keeps the last
known position, and the script says so.

```yaml
script:
  sms_position:
    alias: "SMS: send the position"
    fields:
      number:
        description: Phone number of the receiver
        example: "+491701234567"
    sequence:
      - condition: template
        value_template: >-
          {{ state_attr('device_tracker.my_router_position', 'latitude') is number }}
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "{{ number }}"
          message: >-
            Camper position: https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
            (accuracy {{ state_attr('device_tracker.my_router_position', 'gps_accuracy') | float(0) | round(0) }} m){{
              '' if state_attr('device_tracker.my_router_position', 'fix') else ', no current GPS fix, last known position' }}
```

Call it with `action: script.sms_position` and `data: {number: "+49..."}`.
An SMS counts a part per 160 characters, and a text with umlauts or emoji only
70, so keep the texts plain. The service answers with `sms_used`, how many
parts it took.

## Alarm by SMS when the camper moves

Sends the position by SMS and as a push notification when the camper moves
away from its parking spot while nobody is with it, for example as a theft
warning. It works without internet at the camper, because the SMS goes out
through the router's own SIM; Home Assistant only has to run.

Two checks keep it from raising false alarms:

- **Nobody is with the camper.** The alarm only counts when no person is
  within 500 m of the camper. While you drive, you are with it and nothing
  happens; no switch to turn off.
- **It has to last.** The camper must be more than 200 m from the parking spot
  for 3 minutes in a row, so a wrong GPS reading does not trigger it.

The parking spot is a zone, for example one that follows the camper when you
park (see [Move the home zone with the camper](#move-the-home-zone-with-the-camper)).
Replace `zone.camper_spot`, `person.me` and `person.partner`, and the notify
service and number with your own.

```yaml
automation:
  - alias: "Router: alarm when the camper moves and nobody is with it"
    triggers:
      - trigger: template
        value_template: >-
          {{ distance('device_tracker.my_router_position', 'zone.camper_spot') * 1000 > 200
             and distance('person.me', 'device_tracker.my_router_position') | float(999) > 0.5
             and distance('person.partner', 'device_tracker.my_router_position') | float(999) > 0.5 }}
        for: "00:03:00"
    actions:
      - action: notify.all_mobile_apps
        data:
          title: "ALARM: camper is moving"
          message: "Nobody is with it. Tap for the map."
          data:
            clickAction: >-
              https://www.google.com/maps?q={{
                state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
                state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
      - action: teltonika_control.send_sms
        continue_on_error: true
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "+491701234567"
          message: >-
            ALARM: camper is moving. https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
```

The notification comes first and the SMS has `continue_on_error`, so one
failing does not stop the other. The notification needs Home Assistant to reach
the internet; the SMS does not. To get an update while the camper keeps moving,
add a `time_pattern` trigger (for example every 15 minutes) with the same
conditions. A person without a position counts as far away, so keep the phone
location of the people you want to count switched on.

### With the presence trackers

The check "nobody is with the camper" is more reliable with the
[presence trackers](../README.md#presence-who-is-on-the-wi-fi): a phone on the
Wi-Fi of the router is in the camper, with or without a GPS position. The
automation then needs no person positions, only the trackers of the devices
you chose (replace `device_tracker.me_router` and `device_tracker.partner_router`):

```yaml
automation:
  - alias: "Router: alarm when the camper moves and nobody is on its Wi-Fi"
    triggers:
      - trigger: template
        value_template: >-
          {{ distance('device_tracker.my_router_position', 'zone.camper_spot') * 1000 > 200 }}
        for: "00:03:00"
    conditions:
      - condition: state
        entity_id:
          - device_tracker.me_router
          - device_tracker.partner_router
        state: not_home
    actions:
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "+491701234567"
          message: >-
            ALARM: camper is moving. https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
```

All listed trackers must be `not_home` (the default of a state condition for
several entities). Know the limits: a phone that stays in the camper keeps the
alarm silent, and while the router does not answer the Wi-Fi status the
trackers are `unavailable`, so the condition does not match. The GPS position
comes from the same router, so in that case there is no position either.

## Daily status by SMS

A short status of the camper every morning, for the days without internet: how
the router is connected, how much of the mobile data volume is used, and where
the camper is. Needs the option **Mobile data plan (GB)** for the percentage,
see [Mobile data limit](../README.md#mobile-data-limit). Keep the text under
160 characters, so it stays one SMS.

```yaml
automation:
  - alias: "Router: daily status by SMS"
    triggers:
      - trigger: time
        at: "08:00:00"
    actions:
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "+491701234567"
          message: >-
            Camper: {{ states('sensor.my_router_uplink') }},
            data {{ states('sensor.my_router_data_limit_used_sim_1') | float(0) | round(0) }}%,
            https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(5) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(5) }}
```

The sensors are the ones of the router; use any other entity of Home Assistant
in the same way, for example the battery of the camper or the temperature
inside, to build your own status message.

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
