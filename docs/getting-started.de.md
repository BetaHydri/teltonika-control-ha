# Erste Schritte mit Teltonika Control

[English](getting-started.md) | **Deutsch**

Diese Anleitung führt dich Schritt für Schritt von einem Teltonika-RUTC- oder
-RUTX-Router zu funktionierenden Bedienelementen in Home Assistant. Sie
richtet sich an Home-Assistant-Nutzer, die keine Router-Experten sind. Plane
etwa 15 Minuten ein.

Danach siehst du, welchen Uplink der Router nutzt, wechselst zwischen WLAN
und Mobilfunk, startest die Mobilfunkverbindung neu, fügst WLAN-Netze hinzu
und wirst benachrichtigt, wenn ein Hotspot eine Anmeldung braucht, alles aus
Home Assistant heraus.

<a id="what-you-need"></a>

## Was du brauchst

- Einen Teltonika-RUTC- oder -RUTX-Router mit **RutOS 7**.
- Home Assistant 2025.2 oder neuer. Er muss den Router über das Netzwerk
  erreichen können.
- Die Router-Adresse, zum Beispiel `192.168.1.1`, und eine
  Administrator-Anmeldung für die einmalige Einrichtung des Benutzers.
- Optional: [HACS](https://hacs.xyz/) für einfache Installation und Updates.
- Optional: ein Gerät hinter deinem VPN-Tunnel zum Prüfen, siehe
  [Schritt 12](#step-12-optional-vpn-check).

Die Integration fragt den Router nur ab. Der Router verbindet sich nie mit
Home Assistant und es ist kein Cloud-Konto nötig.

**Es werden keine Home-Assistant-Helfer benötigt.** Die Integration nutzt
keine `input_*`-Helfer, Timer, Zähler, Skripte, Template-Sensoren oder
YAML-Pakete. Alles, auch das Hinzufügen und Entfernen von WLAN-Netzen, ist
eine Entität des Router-Geräts. Helfer brauchst du nur für die optionalen
Extras in [Schritt 11](#step-11-optional-helpers-for-a-monthly-data-counter),
und das Beispiel-Dashboard braucht Frontend-Karten, siehe die
[Dashboard-Anleitung](dashboard.de.md).

<a id="step-1-find-the-router-address"></a>

## Schritt 1: Router-Adresse finden

Nutze die Adresse, die du im Browser öffnest, um die Weboberfläche des
Routers zu erreichen. Meist ist das `192.168.1.1`. Notiere sie dir. Wenn
Home Assistant nicht im eigenen Netz des Routers liegt, stelle sicher, dass
er diese Adresse trotzdem öffnen kann, und erlaube den Zugriff im Router (siehe
Schritt 3).

<a id="step-2-create-a-user-for-home-assistant"></a>

## Schritt 2: Benutzer für Home Assistant anlegen

Verwende für Home Assistant nicht `admin`. Ein eigener Benutzer hält die
Rechte klein und lässt dich den Zugriff später ändern oder entfernen, ohne
deine eigene Anmeldung anzufassen.

1. Öffne die Weboberfläche des Routers und melde dich als Administrator an.
2. Gehe zu **System**, **Administration**, **User Settings**.
3. Lege eine Gruppe für Home Assistant an oder wähle eine vorhandene und gib
   ihr die Rechte aus der Tabelle unten.
4. Lege in dieser Gruppe einen Benutzer mit einem starken, einmaligen Passwort
   an. Lass den SSH-Zugriff für diesen Benutzer ausgeschaltet.
5. Notiere dir Benutzername und Passwort. Du gibst sie in Home Assistant in
   Schritt 5 ein.

Beginne mit **Lese**-Rechten oder gib **Lese- und Schreibrechte** für alle
Bedienelemente. Welche Router-Seite jede Funktion braucht, steht unter
[Router-Benutzer und Berechtigungen](../README.de.md#router-user-and-permissions).

Die Menünamen können sich zwischen RutOS-Versionen leicht unterscheiden.
Teltonika veröffentlicht den genauen Berechtigungseintrag für jede Aktion
nicht, deshalb ordnet die Liste die Aktionen den Router-Seiten zu, zu denen
sie gehören. Wenn Home Assistant später einen Fehler anzeigt, sobald du ein
Bedienelement drückst, kommt die Meldung vom Router: Gib der Gruppe Lese- oder
Schreibrechte auf der passenden Seite und versuche es erneut.

<a id="step-3-allow-access-from-home-assistant"></a>

## Schritt 3: Zugriff von Home Assistant erlauben

Überspringe diesen Schritt, wenn Home Assistant im eigenen Netz des Routers
(LAN) liegt.

Wenn Home Assistant den Router aus einem anderen Netz erreicht, erlaube die
Weboberfläche für dieses Netz unter **System**, **Administration**, **Access
Control**, **General** und in der Firewall des Routers. Öffne die
Weboberfläche des Routers nicht zum Internet. Nutze stattdessen dein LAN oder
ein VPN.

<a id="step-4-test-the-login-from-the-home-assistant-side"></a>

## Schritt 4: Anmeldung von der Home-Assistant-Seite testen

Diese optionale Prüfung spart Zeit, wenn etwas nicht stimmt. Sie zeigt, dass
Adresse, HTTPS-Port und Anmeldung funktionieren, bevor du Home Assistant
anfasst.

Führe auf dem Home-Assistant-Host (zum Beispiel im Terminal-Add-on) die
folgenden Befehle in einer Bash-Shell aus. Sie fragen nach Benutzer und
Passwort, damit das Passwort nicht in deinem Shell-Verlauf landet, und geben
nur aus, ob die Anmeldung funktioniert hat.

```bash
read -p "Router-Benutzer: " U
read -s -p "Router-Passwort: " P; echo
curl -sk -X POST https://192.168.1.1/api/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$U\",\"password\":\"$P\"}" \
  | grep -o '"success":[a-z]*'
unset U P
```

Ersetze `192.168.1.1` durch deine Router-Adresse. `"success":true` heißt, du
bist startklar. `"success":false` deutet auf Benutzername, Passwort oder die
Rechte der Gruppe hin. Gar keine Ausgabe heißt, dass der Router nicht
erreichbar ist; prüfe Adresse, Netzwerk und Schritt 3.

<a id="step-5-install-the-integration"></a>

## Schritt 5: Integration installieren

Mit HACS fügst du `https://github.com/BetaHydri/teltonika-control-ha` als
benutzerdefiniertes Repository vom Typ **Integration** hinzu (Menü
**Benutzerdefinierte Repositories**), installierst **Teltonika Control** und
startest Home Assistant neu. Manuell kopierst du den Ordner
`custom_components/teltonika_control` in den Ordner `custom_components` deiner
Home-Assistant-Konfiguration und startest neu.

<a id="step-6-add-the-router"></a>

## Schritt 6: Router hinzufügen

1. Gehe in Home Assistant zu **Einstellungen**, **Geräte & Dienste**.
2. Wähle **Integration hinzufügen** und suche nach **Teltonika Control**.
3. Fülle das Formular aus:

   | Feld | Was einzugeben ist |
   |---|---|
   | Host | Die Router-Adresse, zum Beispiel `192.168.1.1`. Setze `http://` davor, um reines HTTP zu nutzen. |
   | Benutzername | Der Benutzer aus Schritt 2. |
   | Passwort | Das Passwort dieses Benutzers. |
   | SSL-Zertifikat prüfen | Lass es **aus**, wenn der Router sein eingebautes selbstsigniertes Zertifikat nutzt (der Standard). |

4. Wähle **Senden**.

Home Assistant legt ein Gerät für den Router und ein Gerät für jedes Modem
an. Wenn du einen Fehler siehst, gehe zu [Fehlerbehebung](#troubleshooting).

<a id="step-7-check-what-you-got"></a>

## Schritt 7: Prüfen, was du bekommen hast

Öffne **Einstellungen**, **Geräte & Dienste**, **Teltonika Control** und wähle
das Router-Gerät. Du solltest Folgendes sehen:

- Sensoren für den Uplink und, wenn der Router ein WLAN-Client ist, den
  Netznamen, das Signal, das Band und die Verbindungsgeschwindigkeit, dazu die
  Binärsensoren WLAN verbunden, Internet und Hotspot-Anmeldung nötig.
- Die Auswahl **Uplink-Priorität**, die Schaltflächen **WLAN neu verbinden**
  und **Router neu starten**, je einen Schalter für jeden Access Point und die
  Entitäten zur Verwaltung von WLAN-Netzen (Suche, gefundene Netze, Passwort,
  Hinzufügen, gespeicherte Netze, Entfernen, letzte Aktion).
- Sensoren für den Router-Zustand: **Betriebszeit**, **CPU-Last**,
  **Speicherauslastung** und **DHCP-Clients**.
- Nur wo der Router es bietet: die GPS-**Position** und -Sensoren, die
  VPN-Entitäten ([Schritt 12](#step-12-optional-vpn-check) und
  [Schritt 13](#step-13-optional-restart-a-wireguard-tunnel)), SMS, Firmware,
  Firewall-Schalter und das Datenlimit.

Wähle das Modem-Gerät, um Netzbetreiber, Netzwerktyp, Netzregistrierung,
Signalwerte (RSRP, RSRQ, SINR), Temperatur, SIM-Status und Datenzähler zu
sehen, dazu den Binärsensor **Roaming**, den Schalter **Daten-Roaming SIM 1
erlauben** (je SIM), die Schaltfläche **Mobilfunk neu verbinden** und, bei
Dual-SIM-Modems, die Auswahl **SIM-Slot**. Die vollständige Liste steht unter
[Was du bekommst](../README.de.md#what-you-get).

Manche Entitäten erscheinen nur, wenn der Router sie liefern kann. Die
Prioritätsauswahl braucht mindestens ein gespeichertes WLAN-Client-Netz (siehe
Schritt 9), und Modem-Entitäten brauchen ein Modem mit SIM.

<a id="step-8-build-a-first-dashboard-card"></a>

## Schritt 8: Erste Dashboard-Karte bauen

Entitäts-IDs hängen vom Router-Namen, vom Bereich, in den du ihn legst, und
von deiner Sprache ab. Am einfachsten fügst du die Karte deshalb im
Dashboard-Editor hinzu und wählst die Entitäten aus der Liste. Ein Router mit
dem Namen `RUTC50.lan` im Bereich `IT-Equipment` bekommt bei englischer
Home-Assistant-Sprache zum Beispiel IDs wie
`sensor.it_equipment_rutc50_lan_uplink`; ohne Bereich ist es
`sensor.rutc50_lan_uplink`.

Als Ausgangspunkt schaltest du den Karten-Editor auf **Code-Editor anzeigen**
und fügst Folgendes ein. Es nimmt IDs an, die mit `rutc50_lan` beginnen.
Ersetze diesen Teil durch den Anfang deiner eigenen Entitäts-IDs.

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
    name: Router neu starten (Vorsicht)
```

Füge die Modem-Entitäten auf die gleiche Weise aus dem Modem-Gerät hinzu.
Neustart und SIM-Wechsel unterbrechen die Verbindung, deshalb ist es klug,
sie in deinem Dashboard hinter eine Bestätigung zu legen (eine Button-Karte
mit einem `confirmation`-Eintrag in ihrer Tap-Aktion).

Ein vollständiges, fertiges Dashboard findest du in der
[Dashboard-Anleitung](dashboard.de.md).

<a id="step-9-everyday-tasks"></a>

## Schritt 9: Alltägliche Aufgaben

<a id="switch-between-wi-fi-and-mobile-data"></a>

### Zwischen WLAN und Mobilfunk wechseln

Nutze die Auswahl **Uplink-Priorität**: **WLAN zuerst** oder **Mobilfunk
zuerst**. Der Router braucht mindestens ein gespeichertes WLAN-Client-Netz.
Wenn du WLAN zuerst wählst, verbindet die Integration das WLAN neu, damit die
Änderung wirkt.

Um WLAN zuerst zu bevorzugen und automatisch auf Mobilfunk zurückzufallen,
wenn das WLAN kein Internet hat, rufe die Aktion
`teltonika_control.set_priority` auf:

```yaml
action: teltonika_control.set_priority
target:
  entity_id: sensor.my_router_uplink
data:
  wifi_first: true
  verify: true
```

Nutze als Ziel eine beliebige Entität deines Routers. Ersetze
`sensor.my_router_uplink` durch die Entitäts-ID des Sensors **Uplink** aus
deiner Liste.

<a id="add-a-wi-fi-network"></a>

### WLAN-Netz hinzufügen

Nutze die Entitäten des Router-Geräts, zum Beispiel im
[Dashboard](dashboard.de.md):

1. Drücke **WLANs suchen**. Die Suche dauert pro Radio einige Sekunden.
2. Wähle ein Netz unter **Gefundene WLANs**. Jedes Netz erscheint einmal pro
   Band mit seinem besten Signal, und bereits gespeicherte Netze sind
   ausgeblendet.
3. Tippe das Passwort in **WLAN-Passwort** ein und drücke die Eingabetaste.
   Ein gesichertes Netz braucht ein Passwort mit mindestens 8 Zeichen, bei
   offenen Netzen lässt du es leer. Home Assistant hält das Passwort nur im
   Speicher und zeigt statt des Textes `********`. Im Beispiel-Dashboard
   öffnet die Schlüssel-Schaltfläche am hervorgehobenen Netz dieses Feld.
4. Drücke **Ausgewähltes WLAN hinzufügen**. Ohne Passwort für ein gesichertes
   Netz fordert Home Assistant dich auf, zuerst eines einzugeben.

**Letzte WLAN-Aktion** sagt dir, was passiert ist, zum Beispiel
`Saved CampsiteWifi`. Mobilfunk bleibt bevorzugt, bis du auf **WLAN zuerst**
umschaltest, deshalb unterbricht ein neues Netz nie von selbst deine
Verbindung.

Ein Router-Radio kann nur einen WLAN-Client oder eine Multi-AP-Liste halten.
Ist ein Radio schon belegt, sagt dir die Schaltfläche, welches Netz es
belegt. Bei einem Radio im Multi-AP-Modus (das 5-GHz-Radio des RUTC50) wird
das Netz stattdessen zur Multi-AP-Liste hinzugefügt, siehe
[Multi-AP-Radios](../README.de.md#multi-ap-radios).

Dasselbe geht auch als Aktionen, für Automatisierungen oder Skripte. Führe sie
unter **Entwicklerwerkzeuge**, **Aktionen** aus, mit einer beliebigen Entität
des Routers als Ziel:

```yaml
action: teltonika_control.scan_wifi
target:
  entity_id: sensor.my_router_uplink
```

Die Antwort listet `ssid`, `signal`, `band`, `encrypted` und das `radio`, das
jedes Netz gefunden hat. Speichere eines mit dem `radio` aus der Suche:

```yaml
action: teltonika_control.join_wifi
target:
  entity_id: sensor.my_router_uplink
data:
  radio: radio0
  ssid: CampsiteWifi
  password: "das WLAN-Passwort"
```

<a id="connect-to-a-saved-wi-fi-network"></a>

### Mit einem gespeicherten WLAN-Netz verbinden

Wenn du an einem neuen Ort ankommst, wähle das Netz unter **Gespeicherte
WLANs** und drücke **Ausgewähltes WLAN verbinden**. Der Router probiert dann
dieses Netz sofort, statt zu warten. Ein WLAN-Client wird neu verbunden. Ein
Eintrag einer Multi-AP-Liste wird zuerst an den Anfang der Liste verschoben
(der Router probiert die Liste nach Priorität), und das Multi-AP-Radio
verbindet sich neu.
**Letzte WLAN-Aktion** zeigt `Connecting to ... ...`.

<a id="remove-a-wi-fi-network"></a>

### WLAN-Netz entfernen

Wähle das Netz unter **Gespeicherte WLANs** und drücke **Ausgewähltes WLAN
entfernen**. Die Liste zeigt WLAN-Clients und die Einträge einer
Multi-AP-Liste. Der letzte Multi-AP-Eintrag kann nicht über Home Assistant
entfernt werden.

Als Aktion:

```yaml
action: teltonika_control.forget_wifi
target:
  entity_id: sensor.my_router_uplink
data:
  station_id: "6"
```

Nutze `ssid` statt `station_id` für Netze in einer Multi-AP-Liste.

<a id="use-a-hotspot-that-shows-a-login-page"></a>

### Hotspot mit Anmeldeseite nutzen

Rufe `teltonika_control.portal_mode` auf, öffne `http://neverssl.com` auf
einem Handy, das mit dem Router verbunden ist, und bestätige die Hotspot-Seite.
Wenn der Internettest besteht, bleibt der Router im WLAN. Die Schritte und der
Sensor **Hotspot-Anmeldung** sind unter
[Hotspots mit Anmeldeseite](../README.de.md#hotspots-with-a-login-page)
beschrieben, und es gibt dafür eine
[Beispiel-Benachrichtigung](automation-examples.de.md#hotspot-needs-a-login).

<a id="restart-the-mobile-connection-or-switch-the-sim"></a>

### Mobilfunkverbindung neu starten oder SIM wechseln

Drücke **Mobilfunk neu verbinden** am Modem-Gerät. Bei Dual-SIM-Modems nutze
die Auswahl **SIM-Slot**. Beim Wechsel der SIM fallen die mobilen Daten für
etwa eine Minute aus. Enthält der andere Slot keine SIM, bemerkt die
Integration das (Binärsensor **Keine SIM im aktiven Slot**), wechselt zurück
und zeigt einen Fehler.

<a id="step-10-adjust-the-options"></a>

## Schritt 10: Optionen anpassen

Gehe zu **Einstellungen**, **Geräte & Dienste**, **Teltonika Control** und
wähle dann **Konfigurieren**. Die Standardwerte passen für die meisten
Router. Was jede Option bewirkt, steht unter
[Optionen](../README.de.md#options): die beiden Intervalle (erhöhe beide, wenn
sich ein schwacher Router wie der RUTC50 langsam anfühlt), die URL für den
Internettest, Host und Port für den VPN-Test, das Mobilfunk-Datenvolumen und
die Geräte für die [Anwesenheit](../README.de.md#presence-who-is-on-the-wi-fi).

<a id="show-who-is-in-the-camper"></a>

### Anzeigen, wer im Wohnmobil ist

Wähle in den Optionen unter **Geräte für die Anwesenheit** die Handys deiner
Familie. Ein Handy muss schon einmal mit dem WLAN des Routers verbunden
gewesen sein, damit der Router es kennt und die Liste seinen Namen zeigt.
Füge dann die neuen Tracker (`... (Router)`) den Personen hinzu, unter
**Einstellungen**, **Personen**, **Gerät verfolgen**. Eine Person ist `home`,
solange das Handy im WLAN des Routers ist.

Zwei Einstellungen bestimmen, wie schnell ein Handy, das gegangen ist, als weg
gilt. Der Router behält ein Handy, das sich ohne Abmelden entfernt hat,
mehrere Minuten (oft 5) in seiner Liste. **Anwesenheit: Sekunden Stille bis
„weg“** (Standard 0, aus) verkürzt das: Ein Handy, das so lange nichts
gesendet hat, gilt als gegangen. Wähle den Wert anhand des Attributs
`inactive_seconds` des Trackers und nicht unter 120. **Anwesenheit: Minuten
bis „weg“** (Standard 1) ist eine zusätzliche Wartezeit obendrauf, damit ein
Handy im Standby den Tracker nicht flattern lässt. Eine Person mit dem
Router-Tracker ist `home` mit den Koordinaten der Zone Zuhause, nicht des
Handys; beachte das bei Automatisierungen, die eine Entfernung zu einer Person
messen.
Mehr unter [Anwesenheit](../README.de.md#presence-who-is-on-the-wi-fi).

<a id="step-11-optional-helpers-for-a-monthly-data-counter"></a>

## Schritt 11: Optionale Helfer für einen monatlichen Datenzähler

Dieser Schritt ist optional. Wenn du im Router ein **Datenlimit** setzt, zeigt
die Integration den Datenverbrauch und den Prozentwert bereits an, siehe
[Mobilfunk-Datenlimit](../README.de.md#mobile-data-limit). Ohne Limit hat die
Integration keinen eigenen Monatszähler, aber die Sensoren **Empfangene Daten**
und **Gesendete Daten** des Modems zählen aufwärts, sodass ein eingebauter
Helfer vom Typ Verbrauchszähler (Utility Meter) sie in Monatswerte umwandeln
kann. Mache das einmal für jeden der beiden Sensoren:

1. Gehe zu **Einstellungen**, **Geräte & Dienste**, **Helfer**.
2. Wähle **Helfer erstellen**, dann **Verbrauchszähler** (Utility Meter).
3. Gib einen **Namen** ein, zum Beispiel `Mobile data received monthly`.
4. Wähle den Modem-Sensor **Empfangene Daten** (oder **Gesendete Daten**) als
   **Eingangssensor**.
5. Setze den **Zähler-Reset-Zyklus** auf **Monatlich**. Lass die anderen
   Optionen aus.
6. Wähle **Senden**.

Der neue Sensor beginnt bei null und wird zu Beginn jedes Monats
zurückgesetzt. Für den Gesamtverkehr fügst du einen Helfer **Summe** hinzu
(**Helfer erstellen**, **Zustand mehrerer Sensoren kombinieren**) über die
beiden Zähler. Für eine Warnung bei einem Limit legst du eine Automatisierung
mit einem numerischen Zustands-Auslöser auf diesem Sensor an.

Diese Helfer gehören dir, nicht der Integration. Das Entfernen der Integration
entfernt sie nicht.

<a id="step-12-optional-vpn-check"></a>

## Schritt 12: Optionaler VPN-Test

Dieser Schritt ist optional. Nutze ihn, wenn der Router ein Site-to-Site-VPN
trägt (zum Beispiel WireGuard, OpenVPN oder IPsec) und du in Home Assistant
wissen willst, ob der Tunnel Datenverkehr führt. Es werden kein Helfer und
keine zusätzliche Router-Einstellung benötigt.

1. Wähle ein Gerät am anderen Ende des Tunnels, das immer eingeschaltet ist,
   zum Beispiel den Router zu Hause (`192.168.178.1`), mit einer Adresse im
   Netz des Tunnels. Prüfe von einem Gerät im LAN des Routers aus, dass du es
   erreichen kannst, zum Beispiel durch Öffnen seiner Webseite oder mit
   `ping`.
2. Gehe zu **Einstellungen**, **Geräte & Dienste**, **Teltonika Control**,
   wähle **Konfigurieren**, trage die Adresse unter **Host für den VPN-Test**
   ein und einen Port, den das Gerät beantwortet oder ablehnt, unter **Port
   für den VPN-Test**, und sende ab. Die Integration lädt neu.
3. Am Router-Gerät siehst du jetzt **VPN erreichbar** (Binärsensor) und
   **VPN-Latenz** (Sensor, Diagnose). Wenn du das Beispiel-Dashboard nutzt,
   erscheint die VPN-Pille im Bereich Verbindung.

Welche Adresse und welchen Port du wählst und was der Test aussagt und was
nicht, steht in der [README](../README.de.md#vpn-check). Um den Test
auszuschalten, leere das Feld **Host für den VPN-Test** wieder. Die beiden
Entitäten bleiben dann als nicht verfügbar in der Entitätenliste, bis du sie
löschst.

<a id="step-13-optional-restart-a-wireguard-tunnel"></a>

## Schritt 13: Optional: WireGuard-Tunnel neu starten

Dieser Schritt ist optional und braucht eine WireGuard-Instanz im Router
(**Services**, **VPN**, **WireGuard**). In Home Assistant ist keine zusätzliche
Einrichtung nötig: Die Entitäten erscheinen für jede Instanz von selbst.

1. Stelle sicher, dass der Router-Benutzer aus Schritt 2 die
   WireGuard-Konfiguration lesen und ändern darf. Ohne das Recht zum Ändern
   bekommst du weiterhin den Schnittstellenstatus und die Datenzähler, aber
   keinen Schalter und keine Schaltfläche.
2. Öffne das Router-Gerät in Home Assistant. Für eine Instanz mit dem Namen
   `HOMEBASE` siehst du **WireGuard HOMEBASE**, **WireGuard HOMEBASE
   aktiviert**, **WireGuard HOMEBASE neu verbinden** und die Datenzähler.
3. Drücke zum Testen **WireGuard HOMEBASE neu verbinden**. Der Router schaltet
   die Instanz aus, wartet einige Sekunden und schaltet sie wieder ein. Der
   Datenverkehr durch den Tunnel ist in dieser Zeit unterbrochen, teste es
   also nicht, während du über diesen Tunnel mit dem Router verbunden bist.

Was die Entitäten bedeuten, warum die Schaltfläche ablehnen kann und wie du den
Tunnel automatisch neu startest, wenn der [VPN-Test](#step-12-optional-vpn-check)
fehlschlägt, steht unter
[WireGuard-Tunnel](../README.de.md#wireguard-tunnels).

<a id="troubleshooting"></a>

## Fehlerbehebung

| Symptom | Wahrscheinliche Ursache und Lösung |
|---|---|
| „Verbindung fehlgeschlagen“ beim Hinzufügen des Routers | Home Assistant kann den Router nicht erreichen. Prüfe die Adresse, führe den Test aus Schritt 4 aus und prüfe Schritt 3. Wenn der Router nur HTTP anbietet, setze `http://` vor den Host. |
| „Ungültige Anmeldedaten“ | Falscher Benutzername oder falsches Passwort, oder der Benutzer darf die API nicht nutzen. Prüfe den Benutzer in Schritt 2. Nach vielen falschen Versuchen kann der Router die Adresse eine Weile sperren; prüfe **System**, **Administration**, **Access Control**, **Security**. |
| Home Assistant fordert dich auf, dich erneut anzumelden | Das gespeicherte Passwort wurde abgelehnt, zum Beispiel nachdem du es im Router geändert hast. Gib das neue Passwort im Dialog ein. |
| Router-Adresse hat sich geändert | Nutze **Neu konfigurieren** an der Integration, um die neue Adresse einzugeben. |
| Manche Entitäten fehlen | Modem-Entitäten brauchen ein Modem mit SIM. Die Prioritätsauswahl braucht ein gespeichertes WLAN-Client-Netz. WLAN-Sensoren brauchen WLAN-Hardware. |
| Eine Schaltfläche oder Aktion schlägt mit einer Meldung vom Router fehl | Dem Benutzer fehlt ein Recht. Gib der Gruppe Schreibzugriff auf die passende Seite (Schritt 2). |
| `join_wifi` meldet, dass ein Radio schon einen Client hat | Der Router erlaubt pro Radio einen Client oder eine Multi-AP-Liste. Entferne zuerst den vorhandenen oder nutze das andere Radio. |
| Der Sensor Internet ist aus, obwohl der Router Internet hat | Home Assistant erreicht das Internet womöglich nicht über diesen Router, oder dein Netzwerk blockiert die URL des Tests. Ändere die URL in den Optionen oder leere sie. |
| VPN erreichbar ist aus, obwohl der Tunnel funktioniert | Das gewählte Gerät oder der Port antwortet nicht. Wähle ein immer eingeschaltetes Gerät im Netz des Tunnels und einen Port, den es beantwortet oder ablehnt (eine Firewall, die den Port stillschweigend verwirft, sieht wie ein toter Tunnel aus). Nutze nicht den WireGuard-Endpunkt und seinen UDP-Port, TCP erreicht ihn nie. Prüfe, dass Home Assistant selbst das entfernte Netz über diesen Router erreicht. |
| VPN erreichbar ist an, obwohl der Tunnel tot aussieht | Der Name oder die Adresse löst zu einem Gerät im lokalen Netz auf, oder Home Assistant erreicht das entfernte Netz über einen anderen Weg. Nutze eine Adresse, die nur hinter dem Tunnel existiert. |
| Keine Entitäten für Betriebszeit, CPU-Last, DHCP-Clients oder WireGuard | Der Router-Benutzer darf diese Seiten womöglich nicht lesen (der Router antwortet mit einem Fehler), oder der Router hat keine WireGuard-Instanz. Gib der Gruppe Lesezugriff, siehe Schritt 2, und lade die Integration neu. |
| Ein WireGuard-Tunnel hat keinen Schalter und keine Schaltfläche zum Neuverbinden | Der Benutzer darf **Services**, **VPN**, **WireGuard** womöglich nicht lesen und ändern. Gib der Gruppe dort Lese- und Schreibrechte und lade die Integration neu. |
| **WireGuard … neu verbinden** meldet, der Tunnel sei ausgeschaltet | Die Schaltfläche zum Neuverbinden funktioniert nur bei einem eingeschalteten Tunnel. Schalte stattdessen den Schalter **WireGuard … aktiviert** ein. |
| **Daten-Roaming SIM … erlauben** meldet, der Router habe die Einstellung nicht übernommen | Der Router hat die Änderung nicht übernommen, oder der Benutzer darf die Mobilfunk-Einstellungen nicht ändern. Prüfe **Network**, **Mobile**, **General**, **SIM configuration** im Router und gib der Gruppe Lese- und Schreibrechte auf dieser Seite. |
| Es gibt keinen Schalter **Daten-Roaming SIM … erlauben** | Der Router hat die Seite mit den SIM-Einstellungen nicht beantwortet (der Benutzer darf sie womöglich nicht lesen), oder das Modem ist offline. Gib der Gruppe Lesezugriff auf **Network**, **Mobile**, **General** und lade die Integration neu. |
| Manche Werte aktualisieren sich nicht und das Log meldet „The router did not answer for ... in time“ | Eine Seite des Routers (oft der WLAN-Status) ist langsam oder hängt. Die Integration behält die letzten bekannten Werte dieser Seite, fragt nach zwei Minuten erneut und lässt alle anderen Entitäten weiterlaufen. Wenn sie sich nicht erholt, starte das WLAN des Routers oder den Router neu. |
| Werte sehen falsch aus oder eine Entität bleibt leer | Feldnamen unterscheiden sich zwischen RutOS-Versionen leicht. Lade die Diagnose herunter und eröffne ein Issue. |

<a id="download-diagnostics"></a>

### Diagnose herunterladen

Gehe zu **Einstellungen**, **Geräte & Dienste**, **Teltonika Control**, öffne
das Menü (drei Punkte) des Eintrags und wähle **Diagnose herunterladen**. Aus
der Datei sind das Passwort und andere persönliche Daten entfernt. Sie listet
außerdem, welche Seiten des Routers geantwortet haben, welche fehlen und wie
jede Antwort aufgebaut ist (Schlüsselnamen und Typen, keine Werte). Hänge sie
an ein Issue an.

<a id="turn-on-debug-logging"></a>

### Debug-Protokollierung einschalten

Das Debug-Log erklärt, was die Integration den Router gefragt hat, was zurückkam
und was sie entschieden hat. Es ist die beste Hilfe, wenn eine Funktion auf
deinem Router-Modell nicht funktioniert.

1. Gehe zu **Einstellungen**, **Geräte & Dienste**, **Teltonika Control**.
2. Öffne das Menü (drei Punkte, oben rechts) und wähle **Debug-Protokollierung
   aktivieren**.
3. Reproduziere das Problem, zum Beispiel indem du die Schaltfläche drückst,
   die nicht funktioniert.
4. Öffne dasselbe Menü und wähle **Debug-Protokollierung deaktivieren**. Dein
   Browser lädt die Log-Datei herunter.
5. Öffne die Datei, prüfe sie (siehe unten) und hänge sie an ein Issue an.

Dasselbe lässt sich in der `configuration.yaml` setzen, gefolgt von einem
Neustart von Home Assistant. Entferne es danach wieder:

```yaml
logger:
  logs:
    custom_components.teltonika_control: debug
```

Worauf du achten sollst und was das Log nie enthält, steht in der
[README](../README.de.md#debug-logging).

<a id="update-and-remove"></a>

## Aktualisieren und entfernen

- **Aktualisieren**: Installiere mit HACS die neue Version und starte Home
  Assistant neu. Ersetze bei einer manuellen Installation den Ordner und starte
  neu.
- **Entfernen**: Gehe zu **Einstellungen**, **Geräte & Dienste**, **Teltonika
  Control**, öffne das Menü des Eintrags und wähle **Löschen**. Lösche danach
  den Router-Benutzer aus Schritt 2, wenn du ihn nicht mehr brauchst.

<a id="see-also"></a>

## Siehe auch

- [README](../README.de.md) für die vollständige Liste der Entitäten und
  Dienste.
- [Changelog](../CHANGELOG.de.md)
- [Teltonika-API-Dokumentation](https://developers.teltonika-networks.com/)
