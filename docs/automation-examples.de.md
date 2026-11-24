# Automatisierungsbeispiele

[English](automation-examples.md) | **Deutsch**

Fertige Automatisierungen für Teltonika Control. Ersetze `my_router` durch das
Entitäten-Präfix deines Routers (siehe **Einstellungen, Geräte & Dienste,
Teltonika Control, Entitäten**; in einer anderen Sprache unterscheiden sich die
Endungen) und den Notify-Dienst durch deinen eigenen. Aktionen nehmen jede
Entität des Routers als Ziel.

Die Regeln dahinter stehen auf der Seite
[Best Practices](best-practices.de.md).

- [Warnung vor aufgebrauchtem Mobilfunk-Datenvolumen](#mobile-data-volume-warning)
- [Hotspot braucht eine Anmeldung](#hotspot-needs-a-login)
- [WLAN verloren](#wi-fi-lost)
- [Uplink gewechselt](#uplink-changed)
- [Jemand kommt im Camper an oder verlässt ihn](#somebody-arrives-in-or-leaves-the-camper)
- [Zurück auf Mobilfunk, wenn das WLAN kein Internet hat](#back-to-mobile-data-when-the-wi-fi-has-no-internet)
- [VPN nach Hause ist unterbrochen](#vpn-to-home-is-down)
- [WireGuard-Tunnel neu starten](#restart-the-wireguard-tunnel)
- [Eine neue SMS weiterleiten](#forward-a-new-sms)
- [Eine SMS per Knopfdruck senden](#send-an-sms-from-a-button)
- [Die eingetippte SMS aus einem Skript senden](#send-the-typed-sms-from-a-script)
- [Befehle per SMS](#commands-by-sms)
- [Eine SMS senden, wenn das Datenvolumen knapp wird](#send-an-sms-when-the-data-volume-runs-low)
- [Die Position per SMS senden](#send-the-position-by-sms)
- [Alarm per SMS, wenn sich der Camper bewegt](#alarm-by-sms-when-the-camper-moves)
  ([mit den Anwesenheits-Trackern](#with-the-presence-trackers))
- [Tagesstatus per SMS](#daily-status-by-sms)
- [Neue Firmware nachts herunterladen](#download-new-firmware-at-night)
- [Die Heimatzone mit dem Camper verschieben](#move-the-home-zone-with-the-camper)

<a id="mobile-data-volume-warning"></a>

## Warnung vor aufgebrauchtem Mobilfunk-Datenvolumen

Benötigt die Option **Mobilfunk-Datenvolumen (GB)**, siehe
[Mobilfunk-Datenlimit](../README.de.md#mobile-data-limit). Ist das Volumen
gesetzt, ist der Prozentwert der Anteil deines Vertrags, du kannst dich also an
jedem beliebigen Punkt selbst warnen, ohne die SMS-Warnung des Routers und ohne
Helfer. Die Automatisierung benachrichtigt dich bei 80 und bei 95 Prozent und
nennt das verbleibende Volumen:

```yaml
alias: Warnung Mobilfunk-Datenvolumen
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
      title: "Mobilfunk-Daten: {{ trigger.id }} Prozent verbraucht"
      message: >-
        {{ states('sensor.my_router_data_used_sim_1') | float(0) | round(1) }} GB
        von {{ states('sensor.my_router_data_limit_sim_1') | float(0) | round(1) }} GB
        verbraucht. Der Zähler wird am
        {{ as_timestamp(states('sensor.my_router_data_limit_reset_sim_1'), 0)
           | timestamp_custom('%d.%m.', true) }} zurückgesetzt.
```

Ein Numeric-State-Trigger löst einmal aus, wenn der Wert die Schwelle
überschreitet, und im nächsten Monat erneut, nachdem der Router seinen Zähler
zurückgesetzt hat. Die Bedingung hält ihn nach einem Neustart von Home
Assistant ruhig: Der Sensor wechselt dann von `unknown` auf seinen echten Wert,
was sonst als Überschreitung zählen und die Warnung erneut senden würde. Das
Datenlimit des Routers muss nur aktiviert sein, damit er mitzählt; die Warnung
hängt weder von seiner SMS-Warnung noch von seiner Abschaltung ab.

<a id="hotspot-needs-a-login"></a>

## Hotspot braucht eine Anmeldung

Siehe [Hotspots mit Anmeldeseite](../README.de.md#hotspots-with-a-login-page).
Die Automatisierung benachrichtigt dich, wenn das WLAN verbunden ist, aber drei
Minuten lang kein Internet hat:

```yaml
automation:
  - alias: "Router: Hotspot braucht Anmeldung"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_hotspot_login_required
        to: "on"
        for: "00:03:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: Hotspot-Anmeldung nötig
          message: Öffne http://neverssl.com und bestätige die Seite.
```

<a id="wi-fi-lost"></a>

## WLAN verloren

Dasselbe Muster mit der WLAN-Verbindung. Der Trigger löst nur bei einem echten
Wechsel von `on` auf `off` aus, ein Neustart von Home Assistant sendet also
nichts:

```yaml
automation:
  - alias: "Router: WLAN verloren"
    triggers:
      - trigger: state
        entity_id: binary_sensor.my_router_wifi_connected
        from: "on"
        to: "off"
        for: "00:02:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: WLAN verloren
          message: "Uplink: {{ states('sensor.my_router_uplink') }}"
```

<a id="uplink-changed"></a>

## Uplink gewechselt

Meldet dir jeden Wechsel, zum Beispiel von WLAN auf Mobilfunk, und ignoriert
den Neustart des Routers:

```yaml
automation:
  - alias: "Router: Uplink gewechselt"
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

<a id="somebody-arrives-in-or-leaves-the-camper"></a>

## Jemand kommt im Camper an oder verlässt ihn

Sind die Handys als
[Anwesenheit](../README.de.md#presence-who-is-on-the-wi-fi) ausgewählt und den
Personen hinzugefügt, wechselt eine Person zwischen `home` und `not_home`,
wenn das Handy das WLAN des Routers betritt oder verlässt. In einem Home
Assistant, der im Camper läuft, bedeutet `home` im Camper. Die Automatisierung
meldet dir, wenn jemand ankommt:

```yaml
automation:
  - alias: "Camper: jemand ist angekommen"
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
          message: "{{ trigger.to_state.name }} ist im Camper"
```

Die Tracker der Integration, zum Beispiel `device_tracker.laptop_router`,
lassen sich auch direkt in einer Bedingung oder einem Trigger verwenden.

<a id="back-to-mobile-data-when-the-wi-fi-has-no-internet"></a>

## Zurück auf Mobilfunk, wenn das WLAN kein Internet hat

```yaml
automation:
  - alias: "Router: Mobilfunk zuerst, wenn das WLAN tot ist"
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

<a id="vpn-to-home-is-down"></a>

## VPN nach Hause ist unterbrochen

Warnt, wenn der Tunnel fünf Minuten lang unterbrochen ist, während der Router
online ist. Siehe [VPN-Test](../README.de.md#vpn-check).

```yaml
automation:
  - alias: "Router: VPN nach Hause ist unterbrochen"
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
          message: "Der VPN-Tunnel nach Hause ist unterbrochen, obwohl der Router online ist."
```

<a id="restart-the-wireguard-tunnel"></a>

## WireGuard-Tunnel neu starten

Startet den Tunnel neu, wenn der VPN-Test fünf Minuten lang fehlschlägt,
während der Router Internet hat. Siehe
[WireGuard-Tunnel](../README.de.md#wireguard-tunnels).

```yaml
automation:
  - alias: "Router: WireGuard-Tunnel nach Hause neu starten"
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

Die Verzögerung verhindert, dass die Automatisierung den Tunnel sofort wieder
neu startet, denn der Standardmodus `single` ignoriert neue Trigger, solange
sie läuft.

<a id="forward-a-new-sms"></a>

## Eine neue SMS weiterleiten

Jede neue SMS auf dem Router löst das Ereignis `teltonika_control_sms_received`
aus, siehe [SMS](../README.de.md#sms). Die Automatisierung leitet sie mit dem
Absender im Titel an dein Handy weiter. Nachrichten, die beim Start schon auf
dem Router waren, werden nicht gemeldet.

```yaml
automation:
  - alias: "Router: neue SMS weiterleiten"
    mode: queued
    triggers:
      - trigger: event
        event_type: teltonika_control_sms_received
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: "SMS von {{ trigger.event.data.sender }}"
          message: "{{ trigger.event.data.message }}"
```

Um nur auf einen Absender zu reagieren, ergänze
`event_data: {sender: "+491701111111"}` im Trigger.

<a id="send-an-sms-from-a-button"></a>

## Eine SMS per Knopfdruck senden

Für eine Nachricht, die du oft sendest, etwa „Sind angekommen“, ist ein Skript
mit fester Nummer und festem Text einfacher als Tippen. Starte es über eine
Dashboard-Schaltfläche, ein Widget oder per Sprache. Das Senden kostet, was
eine SMS auf der SIM kostet.

```yaml
script:
  sms_arrived:
    alias: "SMS: angekommen"
    sequence:
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "+491701234567"
          message: "Wir sind angekommen. Der Camper steht."
```

Füge im Dashboard eine Button-Karte hinzu, die `script.sms_arrived` startet,
und verlange eine Bestätigung (`tap_action` mit `confirmation`).

<a id="send-the-typed-sms-from-a-script"></a>

## Die eingetippte SMS aus einem Skript senden

Die Entitäten **SMS-Nummer**, **SMS-Text** und **SMS senden** (siehe
[SMS](../README.de.md#sms)) lassen sich auch aus einem Skript nutzen, zum
Beispiel um die Felder aus einer Aktion einer Companion-App-Benachrichtigung
oder aus einem Helfer zu füllen und in einem Schritt zu senden:

```yaml
script:
  sms_from_helpers:
    alias: "SMS: Helfer-Text senden"
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

Schlägt das Senden fehl (keine Nummer, kein Text, der Router lehnt ab), bricht
das Skript mit dem Grund ab, und der Sensor **SMS-Sendeergebnis** zeigt ihn
ebenfalls an. Für einen Text, der von einem Template abhängt, ist die Aktion
`send_sms` kürzer: Sie nimmt Nummer und Nachricht in einem Aufruf entgegen und
gibt zurück, wie viele SMS-Teile sie belegt hat.

<a id="commands-by-sms"></a>

## Befehle per SMS

Eine SMS kann am Camper etwas auslösen, wenn es kein Internet gibt, zum
Beispiel „Heizung an“. Weil jeder, der die Nummer kennt, eine solche SMS senden
könnte, **prüfe immer den Absender** und halte den Befehl harmlos (der Absender
allein ist kein Beweis, siehe den Hinweis unter dem Beispiel). Die
Automatisierung schaltet die Heizung ein und antwortet dem Absender mit einer
SMS:

```yaml
automation:
  - alias: "Router: SMS-Befehl Heizung an"
    mode: queued
    triggers:
      - trigger: event
        event_type: teltonika_control_sms_received
        event_data:
          sender: "+491701111111"
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.message | trim | lower == 'heizung an' }}"
    actions:
      - action: climate.turn_on
        target:
          entity_id: climate.camper_heating
      - action: teltonika_control.send_sms
        target:
          entity_id: sensor.my_router_sms_messages
        data:
          number: "{{ trigger.event.data.sender }}"
          message: "Heizung ist an."
```

Der Router wird alle zwei Minuten abgefragt, der Befehl kann also bis zu so
lange brauchen, bis er ankommt. Der Absender ist die Nummer, wie das Netz sie
meldet, meist mit Landesvorwahl; prüfe, wie sie im Ereignis erscheint
(Entwicklerwerkzeuge, Ereignisse, auf `teltonika_control_sms_received`
lauschen), bevor du dich auf den Vergleich verlässt. Verwende keine Befehle,
die Schlösser öffnen oder Alarmanlagen ausschalten.

> [!NOTE]
> **Das sind nicht die „SMS Utilities“ des Routers.** Die SMS Utilities von
> RutOS (Services, Mobile Utilities) steuern nur den Router selbst, zum
> Beispiel Neustart, WLAN, Mobilfunk, VPN oder I/O, und sie können Home
> Assistant nicht aufrufen. Die Integration nutzt sie nicht: Sie liest den
> SMS-Posteingang des Routers und löst das Ereignis aus, den Rest erledigt die
> Automatisierung oben. Du musst dafür keine Regel der SMS Utilities aktivieren
> oder konfigurieren.
>
> - **Verwende kein Regel-Schlüsselwort** des Routers (`reboot`, `status`,
>   `mobileoff`, `wifion`, ...) als deinen Befehl. Ist eine solche Regel aktiv
>   und der Text passt (bei „No authorization“ das reine Schlüsselwort,
>   sonst das Schlüsselwort nach dem Autorisierungsschlüssel), führt der
>   Router sie ebenfalls aus.
> - **Die Absendernummer ist kein Geheimnis.** Die Nummer einer SMS kann
>   gefälscht werden. Die SMS Utilities schützen ihre Regeln mit einem
>   Schlüssel im Text (Admin-Passwort, Seriennummer oder eigenes Passwort).
>   Mach es bei einem wichtigen Befehl genauso: Füge dem Text ein geheimes
>   Wort hinzu und prüfe es in der Bedingung, zum Beispiel
>   `value_template: "{{ trigger.event.data.message | trim == 'MeinGeheimnis Heizung an' }}"`.
>   Halte das Geheimnis aus geteilten Automatisierungen und Screenshots heraus.

<a id="send-an-sms-when-the-data-volume-runs-low"></a>

## Eine SMS senden, wenn das Datenvolumen knapp wird

Sendet eine SMS an eine Nummer deiner Wahl, wenn das Volumen deines Tarifs 90
Prozent erreicht, zum Beispiel an ein zweites Handy, wenn niemand die
Benachrichtigung in der App sieht. Benötigt die Option
**Mobilfunk-Datenvolumen (GB)**, siehe
[Mobilfunk-Datenlimit](../README.de.md#mobile-data-limit). Das Senden kostet,
was eine SMS auf der SIM kostet.

```yaml
automation:
  - alias: "Router: SMS bei 90 Prozent des Datenvolumens"
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
            Mobilfunk-Daten: {{ states('sensor.my_router_data_limit_used_sim_1') }} Prozent
            des Tarifs verbraucht.
```

<a id="download-new-firmware-at-night"></a>

## Neue Firmware nachts herunterladen

Hat der Router eine neuere Firmware gefunden, lädt diese Automatisierung sie
nachts herunter und meldet dir, wenn sie bereit ist. Sie **installiert
nichts**: Du entscheidest, wann der Router neu startet, siehe
[Firmware-Update](../README.de.md#firmware-update). Der Download verbraucht
etwas Mobilfunkdaten (die Datei ist etwa 35 MB groß), nutze ihn also mit einem
Datentarif, der das erlaubt, oder nur, solange das WLAN der Uplink ist.

```yaml
automation:
  - alias: "Router: neue Firmware nachts herunterladen"
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
          title: "Router-Firmware heruntergeladen"
          message: >-
            Version {{ state_attr('update.my_router_firmware', 'latest_version') }}
            ist bereit. Installiere sie, wenn der Router zehn Minuten offline sein darf.
```

Die Automatisierung drückt nur die Schaltfläche zum Herunterladen. Drücke
**Firmware installieren** nicht aus einer Automatisierung, es sei denn, du
bist sicher, dass der Router offline sein darf.

<a id="send-the-position-by-sms"></a>

## Die Position per SMS senden

Ein Skript, das die Position des Routers als Google-Maps-Link sendet, für eine
Schaltfläche, einen Sprachbefehl oder eine andere Automatisierung. Der Link
öffnet sich in der Karten-App des empfangenden Handys. Die Position stammt vom
Tracker **Position** des Routers (siehe [GPS](../README.de.md#gps)); ohne Fix
behält der Router die zuletzt bekannte Position, und das Skript weist darauf
hin.

```yaml
script:
  sms_position:
    alias: "SMS: Position senden"
    fields:
      number:
        description: Telefonnummer des Empfängers
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
            Camper-Position: https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
            (Genauigkeit {{ state_attr('device_tracker.my_router_position', 'gps_accuracy') | float(0) | round(0) }} m){{
              '' if state_attr('device_tracker.my_router_position', 'fix') else ', kein aktueller GPS-Fix, zuletzt bekannte Position' }}
```

Rufe es mit `action: script.sms_position` und `data: {number: "+49..."}` auf.
Eine SMS zählt einen Teil pro 160 Zeichen, bei Umlauten oder Emojis nur pro
70, halte die Texte also schlicht. Die Aktion antwortet mit `sms_used`, wie
viele Teile sie belegt hat.

<a id="alarm-by-sms-when-the-camper-moves"></a>

## Alarm per SMS, wenn sich der Camper bewegt

Sendet die Position per SMS und als Push-Benachrichtigung, wenn sich der Camper
von seinem Stellplatz entfernt, während niemand bei ihm ist, zum Beispiel als
Diebstahlwarnung. Es funktioniert ohne Internet am Camper, weil die SMS über
die eigene SIM des Routers hinausgeht; Home Assistant muss nur laufen.

Zwei Prüfungen verhindern Fehlalarme:

- **Niemand ist beim Camper.** Der Alarm zählt nur, wenn sich keine Person
  innerhalb von 500 m um den Camper befindet. Während du fährst, bist du bei
  ihm, und es passiert nichts; kein Schalter zum Ausschalten.
- **Es muss anhalten.** Der Camper muss 3 Minuten am Stück mehr als 200 m vom
  Stellplatz entfernt sein, damit ein falscher GPS-Wert nichts auslöst.

Der Stellplatz ist eine Zone, zum Beispiel eine, die dem Camper folgt, wenn du
parkst (siehe
[Die Heimatzone mit dem Camper verschieben](#move-the-home-zone-with-the-camper)).
Ersetze `zone.camper_spot`, `person.me` und `person.partner` sowie den
Notify-Dienst und die Nummer durch deine eigenen.

```yaml
automation:
  - alias: "Router: Alarm, wenn sich der Camper bewegt und niemand dabei ist"
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
          title: "ALARM: Camper bewegt sich"
          message: "Niemand ist dabei. Tippen für die Karte."
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
            ALARM: Camper bewegt sich. https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
```

Die Benachrichtigung kommt zuerst, und die SMS hat `continue_on_error`, damit
das Scheitern der einen die andere nicht stoppt. Die Benachrichtigung braucht
einen Home Assistant, der das Internet erreicht; die SMS nicht. Für ein Update,
während sich der Camper weiter bewegt, ergänze einen `time_pattern`-Trigger
(zum Beispiel alle 15 Minuten) mit denselben Bedingungen. Eine Person ohne
Position gilt als weit entfernt, lass deshalb die Handy-Ortung der Personen
eingeschaltet, die mitzählen sollen.

<a id="with-the-presence-trackers"></a>

### Mit den Anwesenheits-Trackern

Die Prüfung „niemand ist beim Camper“ ist mit den
[Anwesenheits-Trackern](../README.de.md#presence-who-is-on-the-wi-fi)
zuverlässiger: Ein Handy im WLAN des Routers ist im Camper, mit oder ohne
GPS-Position. Die Automatisierung braucht dann keine Positionen der Personen,
nur die Tracker der Geräte, die du ausgewählt hast (ersetze
`device_tracker.me_router` und `device_tracker.partner_router`):

```yaml
automation:
  - alias: "Router: Alarm, wenn sich der Camper bewegt und niemand in seinem WLAN ist"
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
            ALARM: Camper bewegt sich. https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(6) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(6) }}
```

Alle aufgeführten Tracker müssen `not_home` sein (der Standard einer
Status-Bedingung bei mehreren Entitäten). Kenne die Grenzen: Ein Handy, das im
Camper bleibt, hält den Alarm still, und solange der Router den WLAN-Status
nicht beantwortet, sind die Tracker `unavailable`, die Bedingung trifft also
nicht zu. Die GPS-Position stammt vom selben Router, in diesem Fall gibt es
also auch keine Position.

<a id="daily-status-by-sms"></a>

## Tagesstatus per SMS

Ein kurzer Status des Campers jeden Morgen, für die Tage ohne Internet: wie der
Router verbunden ist, wie viel des Mobilfunk-Datenvolumens verbraucht ist und
wo der Camper steht. Benötigt für den Prozentwert die Option
**Mobilfunk-Datenvolumen (GB)**, siehe
[Mobilfunk-Datenlimit](../README.de.md#mobile-data-limit). Halte den Text unter
160 Zeichen, damit es bei einer SMS bleibt.

```yaml
automation:
  - alias: "Router: Tagesstatus per SMS"
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
            Daten {{ states('sensor.my_router_data_limit_used_sim_1') | float(0) | round(0) }}%,
            https://www.google.com/maps?q={{
              state_attr('device_tracker.my_router_position', 'latitude') | round(5) }},{{
              state_attr('device_tracker.my_router_position', 'longitude') | round(5) }}
```

Die Sensoren sind die des Routers; nutze jede andere Entität von Home Assistant
auf dieselbe Weise, zum Beispiel die Batterie des Campers oder die
Innentemperatur, um deine eigene Statusnachricht zu bauen.

<a id="move-the-home-zone-with-the-camper"></a>

## Die Heimatzone mit dem Camper verschieben

Steht der Router seit zehn Minuten still, folgt der Heimatstandort von Home
Assistant seiner GPS-Position.

```yaml
automation:
  - alias: "Camper: Heimatzone folgt dem Router, wenn geparkt"
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
