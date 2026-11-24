# Changelog

[English](CHANGELOG.md) | **Deutsch**

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
festgehalten.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
und dieses Projekt hält sich an
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.23.2] - 2026-11-23

### Hinzugefügt

- **Anwesenheits-Tracker zeigen `signal` und `inactive_seconds`.** Die
  Signalstärke in dBm und die Sekunden, seit der Router zuletzt vom Gerät
  gehört hat, solange es im WLAN ist. Nutze sie, um den Wert für **Anwesenheit:
  Sekunden Stille bis „weg“** zu wählen. Beide bleiben aus dem Recorder-Verlauf
  heraus.

## [0.23.1] - 2026-11-23

### Behoben

- **Firmware zeigte „ready“ für eine Datei, die der Router nicht mehr hatte.**
  Die Download-Seite des Routers meldet weiter „succeeded“, nachdem die Datei
  gelöscht wurde, zum Beispiel durch einen Neustart des Routers. Der Status
  stand dann stundenlang auf `ready`, und **Firmware installieren** schlug mit
  „Firmware file not found in the device“ fehl. Bevor der Status `ready` sagt,
  prüft die Integration jetzt einmal pro Version, ob die Datei noch auf dem
  Router liegt (der Verify-Schritt der Weboberfläche des Routers, er
  installiert nichts). Eine Datei, die weg ist, hält den Status bei
  `update_available`; jede andere Antwort lässt den Status unverändert, und die
  Prüfung wird später wiederholt. Der Fehler von **Firmware installieren**
  sagt jetzt, was zu tun ist: erst erneut herunterladen.

## [0.23.0] - 2026-11-23

### Hinzugefügt

- **Anwesenheit: das WLAN schneller verlassen.** Ein Handy, das sich ohne
  Abmelden entfernt, bleibt in der Liste des Routers, bis dessen
  Inaktivitätslimit abläuft, oft 5 Minuten, sodass sein Tracker so lange
  `home` blieb. Die neue Option **Anwesenheit: Sekunden Stille bis „weg“**
  (Standard 0, aus) zählt ein Gerät als weg, sobald es so lange nichts
  gesendet hat. Die Debug-Logzeile `Presence: ...` zeigt jetzt `idle_seconds`
  der gewählten Geräte (ohne Adressen), damit du den Wert leichter wählen
  kannst.

## [0.22.0] - 2026-11-23

### Hinzugefügt

- **Anwesenheit über das WLAN.** Wähle in den Optionen Geräte aus (**Geräte für
  die Anwesenheit**, aus der Liste der Geräte, die der Router kennt, oder per
  MAC-Adresse), und die Integration legt für jedes einen Device-Tracker an. Er
  ist `home`, solange das Gerät mit einem der Access Points des Routers
  verbunden ist, und `not_home`, nachdem es **Anwesenheit: Minuten bis „weg“**
  (Standard 1) lang gefehlt hat. Ordne die Tracker in Home Assistant Personen
  zu: Ein Router-Tracker hat Vorrang vor dem GPS des Handys, sodass eine Person
  im Camper `home` ist, sobald das Handy in dessen WLAN ist. Der WLAN-Status
  wird ohnehin bei jeder Aktualisierung gelesen, daher entsteht keine zusätzliche
  Last auf dem Router. Ein Tracker, der aus den Optionen entfernt wird, wird
  aus Home Assistant entfernt; die MAC-Adressen sind in der Diagnose
  verborgen und werden nicht ins Debug-Log geschrieben.

## [0.21.1] - 2026-11-22

### Behoben

- **Das Umschalten der Uplink-Priorität schlug fehl, solange kein WLAN
  verbunden war.** Der Router beantwortete das WLAN-Neuverbinden mit „failed
  to parse interface device“, und Home Assistant zeigte einen Fehler, obwohl
  die neue Priorität bereits gespeichert war, und ein zweites gespeichertes
  Netz wurde ausgelassen. Ein Neuverbinden, das der Router verweigert, stoppt
  die Änderung nicht mehr; die Priorität gilt, wenn das WLAN sich verbindet.

## [0.21.0] - 2026-11-22

### Hinzugefügt

- **Ausgewähltes WLAN verbinden.** Eine Schaltfläche neben **Gespeicherte
  WLANs**, die den Router das ausgewählte gespeicherte Netz jetzt versuchen
  lässt, statt erst nachdem er jedes andere gespeicherte Netz versucht hat,
  zum Beispiel nach einem Umzug auf einen neuen Campingplatz. Ein WLAN-Client
  wird neu verbunden. Ein Eintrag der Multi-AP-Liste wird an die Spitze der
  Liste verschoben (Priorität 1, die anderen folgen in ihrer alten Reihenfolge),
  und das Multi-AP-Radio verbindet neu. Das Beispiel-Dashboard hat eine
  Schaltfläche **Verbinden**.

## [0.20.1] - 2026-11-20

### Behoben

- **Ein zweiter Wechsel auf einen leeren SIM-Slot direkt nach dem ersten wurde
  nicht rückgängig gemacht.** Nach einem Wechsel meldet das Modem noch etwa eine
  halbe Minute den SIM-Status des alten Slots, sodass die Integration den alten
  Slot für leer hielt und den Router auf dem leeren Slot ließ. Eine Messung
  direkt nach einem Wechsel zählt nicht mehr als Status des alten Slots. Ein
  Slot mit SIM wird jetzt erst nach 20 Sekunden und zwei Messungen bestätigt,
  und die Überwachung dauert bis zu 90 Sekunden.

## [0.20.0] - 2026-11-20

### Hinzugefügt

- **Keine SIM im aktiven Slot.** Ein Binärsensor an jedem Modem, der an ist,
  solange der Router den SIM-Status `Not inserted` meldet. Zuvor zeigte sich
  ein leerer Slot nur als unbekannte Signalwerte und „No service“.
- **Ein Wechsel auf einen leeren SIM-Slot wird rückgängig gemacht.** Nachdem
  die Auswahl **SIM-Slot** den Slot umgeschaltet hat, beobachtet die Integration
  das Modem bis zu 90 Sekunden. Enthält der neue Slot keine SIM, schaltet sie
  auf den vorherigen Slot zurück und zeigt einen Fehler. Ist in keinem Slot
  eine SIM, wird nichts zurückgeschaltet. Das Beispiel-Dashboard zeigt eine
  rote Pille, solange der aktive Slot leer ist.

## [0.19.0] - 2026-11-19

### Hinzugefügt

- **Datenverbrauch heute und Datenverbrauch Monat.** Zwei Sensoren mit den
  empfangenen plus gesendeten Mobilfunkdaten des Tages und des Monats, gelesen
  aus der Verkehrsstatistik des Routers. Die Attribute `received_mb` und
  `sent_mb` teilen den Wert auf. Die Sensoren erscheinen, wenn der Router die
  Seiten hat. Das Beispiel-Dashboard zeigt sie als Pillenpaar Heute / Dieser
  Monat.

### Geändert

- **Empfangene Daten und Gesendete Daten sind bei neuen Installationen
  standardmäßig deaktiviert.** Es sind Gesamtzähler des Modems seit Beginn; die
  neuen Tages- und Monatssensoren sind nützlicher. Bestehende Installationen
  behalten ihren Zustand, aktiviere sie in den Entitätseinstellungen, wenn du
  sie willst. Das Beispiel-Dashboard zeigt sie nicht mehr.

## [0.18.1] - 2026-11-19

### Behoben

- **Empfangene und gesendete Daten.** Der Router meldet diese Modemzähler
  gelegentlich für eine einzelne Messung als 0. Home Assistant hielt das für
  einen Zählerreset und addierte die gesamte Summe (mehr als 200 GB) ein
  zweites Mal zu den Langzeitstatistiken. Ein Zähler, der um mehr als 10
  Prozent fällt, wird jetzt gehalten, bis der niedrigere Wert drei Messungen
  lang bestehen geblieben ist, sodass ein echter Reset weiterhin übernommen
  wird.

## [0.18.0] - 2026-11-18

### Hinzugefügt

- **SMS-Posteingang.** Der Sensor **SMS-Nachrichten** listet die neuesten 10
  Nachrichten, die neueste zuerst, in seinem Attribut `messages` (Absender,
  Datum, Status, Text). Das Attribut wird nicht in der Verlaufsdatenbank
  aufgezeichnet. Das Beispiel-Dashboard zeigt es als **Posteingang** unter den
  Feldern des SMS-Pop-ups.

## [0.17.3] - 2026-11-18

### Behoben

- **Firmware-Status nach einem Update.** Sobald der Router die neueste Firmware
  nutzt und keine neuere Version listet, sagte der Status wegen des alten
  „succeeded“ des Routers `ready`. Jetzt sagt er `up_to_date`, auch wenn die
  Versionen nicht verglichen werden können, wie die Update-Entität.
- **Deprecation-Warnung.** Home Assistant meldete, dass die Integration Geräte
  mit `async_get_device` nachschlägt, was in Home Assistant 2027.8 nicht mehr
  funktioniert. Die Abfragen (Erkennung per MAC-Adresse, die neue
  Firmware-Version am Gerät) laufen jetzt über die Geräte des Config Entry.

## [0.17.2] - 2026-11-18

### Behoben

- **Der Firmware-Download holte nichts.** Ein Router, dessen Update-Server kein
  stabiles Release hat (er meldet die Version `newest`), lud nichts herunter,
  wenn die Integration **Firmware herunterladen** drückte, weil der Standardtyp
  des Routers „stable“ ist. Der Download fragt jetzt den Typ an, den er
  braucht, `stable` oder `latest`.
- **Altes „succeeded“ zählte als abgeschlossener Download.** Die Fortschrittsseite
  des Routers behält das Ergebnis eines alten Downloads, sodass der Status
  `ready` sagte, obwohl keine Datei da war, und **Firmware installieren** mit
  „Firmware file not found“ fehlschlug. Nach dem Drücken von **Firmware
  herunterladen** sagt der Status `downloading`, bis die Fortschrittsseite
  nachgezogen hat, und eine fehlende Datei setzt den Status zurück auf
  `update_available`.

## [0.17.1] - 2026-11-18

### Behoben

- **Firmware-Status während eines Downloads.** Wenn der Router die Update-Seite
  während des Downloads nicht mehr beantwortete, wurden die Update-Entität und
  der Sensor **Firmware-Status** `unknown` und die Download-Schaltfläche
  nicht verfügbar, genau dann, wenn der Fortschritt wichtig war. Die zuletzt
  bekannten Update-Informationen bleiben erhalten, solange ein Download oder
  eine Installation verfolgt wird, und der Download-Fortschritt allein reicht
  aus, um `downloading` zu melden.

## [0.17.0] - 2026-11-18

### Hinzugefügt

- **Firmware-Status.** Der Sensor **Firmware-Status** verfolgt das gesamte
  Update: `up_to_date`, `update_available`, `downloading` (mit dem Attribut
  `percent`), `ready`, `installing` und `failed`. Er ersetzt den Sensor
  *Firmware-Download* aus 0.16.0. Er bleibt verfügbar, während der Router für
  eine Installation neu startet, und sagt `installing`; er wird `failed`, wenn
  der Router zehn Minuten nach dem Start noch die alte Version meldet.
- **Neue Version wird erkannt.** Der Router liest die laufende Firmware von
  seiner Firmware-Seite, sodass das Gerät nach einem Update die neue Version
  zeigt, ohne die Integration neu zu laden.

### Behoben

- Die Schaltflächen zum Herunterladen und Installieren sind nicht verfügbar,
  solange eine Installation läuft, und eine abgelehnte Installation bleibt nicht
  mehr in `installing` hängen.

## [0.16.0] - 2026-11-18

### Hinzugefügt

- **Firmware herunterladen und installieren.** Die Schaltfläche **Firmware
  herunterladen** lässt den Router das gefundene Update herunterladen (es wird
  nichts installiert, kein Neustart). Der Sensor *Firmware-Download* zeigt
  Zustand und Prozent, und der Fortschritt wird bei jeder Aktualisierung
  gelesen, solange ein Download läuft. Die Schaltfläche **Firmware
  installieren** installiert die heruntergeladene Firmware unter Beibehaltung
  der Einstellungen; der Router startet neu. Sie ist **standardmäßig
  deaktiviert** und nur verfügbar, wenn ein vollständiger Download auf dem
  Router wartet. Die Update-Entität selbst informiert weiterhin nur. Basiert auf
  der API-Beschreibung von Teltonika; die Installation wurde nicht auf echter
  Hardware ausprobiert.
- **Dashboard.** Die Pille **Firmware** öffnet ein Pop-up mit beiden
  Schaltflächen, jede mit einer Bestätigung. Neues Automationsbeispiel: neue
  Firmware nachts herunterladen.

### Geändert

- **Beispiel-Dashboard.** Die Pille **SMS auf dem Router** öffnet ein Pop-up
  **SMS senden** (Bubble Card) mit den Feldern für Nummer und Text und einer
  Senden-Schaltfläche, die um Bestätigung bittet, sodass SMS gesendet werden
  können, ohne das Haupt-Dashboard zu verlassen. Die Pop-ups nutzen das
  Standalone-Format von Bubble Card 3.2.0 (die enthaltenen Karten stehen unter
  `cards`, kein Vertical Stack nötig).

## [0.15.0] - 2026-11-18

### Hinzugefügt

- **SMS aus dem Dashboard senden.** Die Textfelder **SMS-Nummer** und
  **SMS-Text**, die Schaltfläche **SMS senden** und der Sensor
  **SMS-Sendeergebnis** lassen dich eine SMS ohne Automation schreiben und
  senden. Der Text wird nach erfolgreichem Senden geleert, das Ergebnis sagt
  `Sent` oder warum nicht gesendet wurde. Nur bei Routern mit der SMS-Seite.
  Ein fertiges Dashboard ist `dashboards/teltonika-sms.yaml`.
- **Doku.** Neue Automationsbeispiele: SMS über eine Schaltfläche, die
  getippte SMS aus einem Script senden und Befehle per SMS mit
  Absenderprüfung.

## [0.14.0] - 2026-11-18

### Hinzugefügt

- **Tailscale, OpenVPN, IPsec und SSTP.** Jede Instanz dieser VPN-Typen auf
  dem Router bekommt einen Binärsensor *verbunden* (mit dem Statustext und den
  Zählern als Attribute), einen Schalter *aktiviert* zum Verbinden oder
  Trennen und eine Schaltfläche *Neu verbinden*, die die Instanz aus- und
  wieder einschaltet. Basiert auf der API-Beschreibung von Teltonika; noch
  nicht auf echter Hardware ausprobiert. Das Abmelden von Tailscale wird
  bewusst nicht angeboten.

### Behoben

- **Firmware.** Ein Router ohne stabilen Kanal meldet den Platzhalter `newest`
  als seine stabile Version. Die Firmware-Entität fällt jetzt auf das neueste
  Release zurück, statt den Platzhalter als Version zu behandeln.

## [0.13.0] - 2026-11-18

### Hinzugefügt

- **Im Netzwerk gefunden.** Ein Teltonika-Router, der um eine Adresse bittet,
  erscheint unter *Entdeckt* (MAC-Adressbereiche `20:97:27` und `00:1E:42`,
  dieselben wie bei der Core-Integration). Gib die Anmeldedaten ein, und der
  Router ist eingerichtet. Ein bereits eingerichteter Router wird nicht erneut
  angeboten; ändert sich seine Adresse und antwortet die alte Adresse nicht
  mehr, wird die neue übernommen. Eine Adresse, die noch antwortet, wird nie
  ersetzt, weil ein Router unter mehreren Adressen zu sehen sein kann.
- **MAC-Adressen in der Geräteregistrierung.** Das Router-Gerät trägt seine
  beiden MAC-Adressen, sodass Home Assistant es mit demselben Gerät in anderen
  Integrationen verknüpfen kann.
- **HTTPS, dann HTTP.** Eine Adresse ohne `http://` oder `https://` wird
  zuerst mit HTTPS und dann mit unverschlüsseltem HTTP versucht, sodass ein
  Router, der nur HTTP anbietet, eingerichtet werden kann (auch über *Neu
  konfigurieren* und die Erkennung), ohne das Schema einzutippen.
- **SMS.** Der Dienst `teltonika_control.send_sms` sendet eine SMS über ein
  Modem des Routers und gibt zurück, wie viele SMS-Teile er belegt hat. Der
  Sensor **SMS-Nachrichten** zählt die Nachrichten auf dem Router, und jede
  neue Nachricht löst das Ereignis `teltonika_control_sms_received` mit
  Absender, Text, Datum, Modem und Status aus. Nachrichten, die beim Start
  schon auf dem Router sind, werden nicht gemeldet. Die Nummer und der Text
  werden nie ins Log geschrieben, und die Texte werden nicht in einem Sensor
  gespeichert. Neue Berechtigungszeilen stehen in der README.
- **Firmware.** Eine Update-Entität zeigt die installierte Firmware und das
  neueste stabile Release, das der Router auf seinem Update-Server gefunden
  hat. Sie informiert nur. Die Versionen werden anhand ihrer Zahlen
  verglichen; lassen sie sich nicht vergleichen, steht dort „Aktuell“. Sie
  erscheint nur, wenn der Router Update-Informationen hat.
- **Beispiel-Dashboard:** zwei optionale Pillen unter *Routerzustand*,
  **SMS auf dem Router** und **Firmware**, die sich selbst ausblenden, solange
  die Daten fehlen.
- **Probe-Tool:** fragt zusätzlich die Firmware-Update-Informationen, den
  Speedtest-Status, VRRP, DDNS und den Hotspot-Status ab und zeigt
  Firmware-Versionen, Nachrichtendaten und Speedtest-Werte (keine Namen,
  Nummern oder Nachrichtentexte).

## [0.12.4] - 2026-11-18

### Hinzugefügt

- **Der WLAN-Scan meldet, dass er gestartet ist.** **Letzte WLAN-Aktion** zeigt
  jetzt `Scanning for networks ...`, sobald du **WLANs suchen** drückst, und
  ersetzt es durch das Ergebnis, wenn der Scan fertig ist. Zuvor zeigte die
  Pille für die mehreren Sekunden, die ein Scan dauert, das alte Ergebnis, es
  sah also aus, als passiere nichts. Wird die Schaltfläche erneut gedrückt,
  während ein Scan läuft, wird das ignoriert, statt einen zweiten Scan zu
  starten.

### Geändert

- **Beispiel-Dashboard: Bedienelemente sind auch ohne die Farbe erkennbar.**
  Jede Pille, die etwas auslöst, hat rechts eine kleine Schaltfläche: eine
  Hand für eine einmalige Aktion, einen Schalter für Daten-Roaming (an oder
  aus), einen gefüllten oder leeren Kreis für WLAN zuerst und Mobilfunk zuerst
  und den Text An oder Aus für das eigene WLAN des Routers. Die kleine
  Schaltfläche tut dasselbe wie die Pille, einschließlich der Bestätigung. Die
  Roaming-Pillen heißen jetzt „SIM 1: Roaming an“ und „aus“, damit der Text
  neben den Schalter passt. Siehe
  [docs/dashboard.de.md](docs/dashboard.de.md).

## [0.12.3] - 2026-11-18

### Geändert

- Nur Dokumentation, keine Änderung am Code der Integration. Die Warnung zum
  Datenvolumen in den Automationsbeispielen sendet nach einem Neustart von
  Home Assistant keine Nachricht mehr (der Sensor wechselt von `unknown` auf
  seinen Wert, was als Überschreiten des Schwellwerts zählte) und schlägt nicht
  mehr fehl, solange die Reset-Zeit noch nicht bekannt ist. Die README
  beschreibt die Erkennung einer abgelaufenen Hotspot-Anmeldung und hat eine
  Ein-Klick-Schaltfläche, die das Repository in HACS öffnet.
- Das Release wird aus einer Repository-Historie ohne die Co-authored-by-Zeilen
  früherer Commits erstellt. Die Tags `v0.12.1` und `v0.12.2` sind durch GitHub
  geschützt und zeigen weiter auf die alten Commits; der Code ist derselbe.

## [0.12.2] - 2026-11-17

### Behoben

- **Abgelaufene Hotspot-Anmeldung wird erkannt.** Ein Hotspot, der eine neue
  Anmeldung verlangt (zum Beispiel alle 24 Stunden), lässt die Failover-Prüfung
  des WLANs fehlschlagen, und der Router schickt den Verkehr dann über
  Mobilfunk. Die Internetprüfung von Home Assistant bestand weiterhin, sodass
  **Hotspot-Anmeldung** nie `login_required` zeigte und die Benachrichtigung
  ausblieb. Jetzt zeigt sie `login_required` auch dann, wenn das WLAN verbunden
  ist und das Failover jede WLAN-Schnittstelle als offline meldet. Der
  Portalmodus liest den Failover-Status bei jeder Abfrage, sodass er die
  Anmeldung ohne die übliche Verzögerung bemerkt.
- **Failover `standby` zählt als online.** Der Router meldet eine Schnittstelle,
  die funktioniert, aber nicht genutzt wird (das Backup, während eine andere den
  Verkehr trägt), als `standby`. Das wurde als nicht online gelesen, sodass
  **Failover Mobilfunk online** aus zeigte, ebenso die Dashboard-Pille
  „Mobilfunk offline“, obwohl WLAN der Uplink war und der Mobilfunk in Ordnung
  war. `standby` ist jetzt online; `offline` bleibt offline, und `starting`
  oder `notracking` sagen nichts aus.

## [0.12.1] - 2026-11-17

### Behoben

- **Der Sensor Uplink folgt dem Failover.** Er zeigte die Schnittstelle mit der
  besten Metrik auch dann, wenn das Failover des Routers sie als offline
  meldete, sodass ein WLAN, dessen Hotspot die Check-Pings blockiert, als
  Uplink angezeigt wurde, während der Verkehr über Mobilfunk lief. Jetzt wird
  eine Schnittstelle, die das Failover als offline meldet, übergangen
  (Attribut `failover_skipped`). Sind alle Schnittstellen offline, entscheidet
  wie bisher die Metrik.
- **GPS ohne Fix.** Die Position bleibt jetzt auf der zuletzt bekannten, statt
  `unknown` zu werden, auch über einen Neustart von Home Assistant hinweg. Der
  Satellitensensor zeigt 0 statt `unknown`, wenn der Empfänger keinen Fix hat.

### Hinzugefügt

- Binärsensor **GPS-Empfang**: an, solange der Empfänger einen Fix hat.
  Attribute: genutzte Satelliten und der Zeitpunkt des letzten Fixes. Der
  Device-Tracker erhält die Attribute `fix` und `last_fix`.

## [0.12.0] - 2026-11-17

### Hinzugefügt

- **Option für den Mobilfunk-Datentarif.** In den Optionen kannst du das
  monatliche Volumen deines Mobilfunkvertrags in GB eingeben. Der Prozentwert,
  der Sensor **Datenlimit**, der Sensor **Datenlimit erreicht** und die
  Dashboard-Pillen beziehen sich dann auf deinen Tarif statt auf das Datenlimit
  des Routers. Das passt zu Anbietern, die die Verbindung drosseln, wenn das
  Volumen aufgebraucht ist: Das Limit des Routers kann hoch gesetzt werden,
  sodass der Router den Mobilfunk nie abschaltet und nur mitzählt. Ohne die
  Option ändert sich nichts. Der Tarif rechnet 1 GB als 1000 MB, das Limit des
  Routers rechnet 1 MB als 1.048.576 Bytes; die README erklärt den
  Unterschied.

## [0.11.0] - 2026-11-17

### Hinzugefügt

- **Schalter für Traffic-Regeln.** Ein Schalter **Firewall-Regel *Name*** für
  jede Regel in `/firewall/traffic_rules/config`, der die Regel ein- oder
  ausschaltet. Es wird nur das Feld `enabled` geschrieben, und die Einstellung
  wird nach der Änderung zurückgelesen, wie bei den Schaltern für
  Portweiterleitungen. Die Attribute sagen, was die Regel tut: `kind`,
  `group`, `source_zone`, `destination_zone`, `protocol`, `ports`, `action`.
  Die eigenen Regeln des Routers (mit Namen `Allow-...`, Gruppe `system`)
  werden **deaktiviert** angelegt, weil das versehentliche Ausschalten einer
  davon eine Verbindung kappen kann; aktiviere die gewünschten in den
  Entitätseinstellungen.
- **Firewall-Zähler.** **Offene Portweiterleitungen** und **Firewall-Regeln
  zum Internet offen** zählen, was an ist, und listen die Namen im Attribut
  `rules`, zum Beispiel für eine Warnung, wenn etwas offen bleibt.
- **Firewall-Dashboard.** Ein eigenes Dashboard für die Portweiterleitungen und
  Traffic-Regeln, `dashboards/teltonika-firewall.yaml`, mit einer Anleitung in
  `docs/firewall-dashboard.de.md`: Die Regeln des Routers werden von selbst
  aufgelistet, gruppiert in Portweiterleitungen, Zugriff auf den Router aus dem
  Internet und Weiterleitung ins Netzwerk. Jeder Schalter fragt nach einer
  Bestätigung. Es braucht die Frontend-Karten Mushroom und auto-entities. Die
  Anleitung zeigt außerdem eine Version ohne auto-entities, eine Pop-up-Version
  und eine Automation, die warnt, wenn ein Port offen bleibt.
- Die Schalter für Portweiterleitungen haben das Attribut `kind`
  (`port_forward`), das das Firewall-Dashboard nutzt, um sie zu finden.

### Geändert

- Das Haupt-Beispiel-Dashboard hat keine Pille mehr für eine einzelne
  Portweiterleitung. Es hat eine Pille **Firewall**, die das Firewall-Dashboard
  öffnet, grün, solange nichts zum Internet offen ist, und orange, solange eine
  Portweiterleitung oder eine Regel an ist. Sie erscheint nur, wenn der Router
  solche Regeln hat.

### Behoben

- Home Assistant protokollierte eine Deprecation-Warnung, wenn ein Dienst
  genutzt wurde: `DeviceEntry.config_entries` wird durch `config_entry_id`
  ersetzt. Das Dienstziel nutzt jetzt das neue Attribut und funktioniert
  weiterhin auf älteren Versionen.

### Hinweise

- Die Seite der Traffic-Regeln ist wie die anderen neuen Seiten optional: Ein
  Router oder Benutzer ohne sie bekommt keine Firewall-Regel-Entitäten, und
  alles andere funktioniert weiter.

## [0.10.1] - 2026-11-17

### Hinzugefügt

- **Failover nach Art.** Ein Binärsensor pro Art von Uplink, die in der
  Failover-Konfiguration des Routers existiert: **Failover Mobilfunk online**,
  **Failover WLAN online** und **Failover Ethernet online**. Jeder ist an,
  solange irgendeine Schnittstelle dieser Art online ist. Die Entität hat auf
  jedem Router denselben Namen, sodass Dashboards und Automationen keine
  Schnittstellennamen brauchen.

### Behoben

- Die Failover-Entitäten lesen jetzt aus der Failover-Konfiguration des
  Routers, was jede Schnittstelle ist (`/failover/interfaces/config`: Typ
  `mobile`, `wireless` oder `wired`, und der Schnittstellenname). Ein RUTC50
  listet seine WLAN-Netze dort als `wan2` und `wan3`; 0.10.0 benannte sie nach
  diesen IDs und konnte nicht erkennen, dass es WLAN ist. Sie heißen jetzt zum
  Beispiel „WLAN (wifi4)“. Die Entitäts-IDs bestehender Entitäten ändern sich
  nicht.
- Doku: Die Failover-Prüfung des Routers pingt ihre Prüfadressen durch die
  Schnittstelle, sodass ein WLAN, das diese Pings blockiert, `offline` zeigt,
  während es Verkehr trägt. Die README sagt das, und das Beispiel-Dashboard hat
  keine WLAN-Failover-Pille.

### Geändert

- Die Failover-Pille des Beispiel-Dashboards nutzt **Failover Mobilfunk
  online** und enthält keinen Schnittstellennamen mehr.

## [0.10.0] - 2026-11-17

### Hinzugefügt

- **Failover-Status.** Für jede Schnittstelle in der Failover-Konfiguration des
  Routers ein Sensor **Failover *Schnittstelle*** (der Text des Routers:
  online, offline, standby, starting, notracking; Attribute Health Score,
  Sekunden seit der letzten Änderung, Sekunden online und offline und
  verlorene Tracking-Probes) und ein Binärsensor **Failover *Schnittstelle*
  online**. Gelesen von `/failover/status`, das mit einem Dictionary antwortet,
  dessen Schlüssel die Schnittstellennamen sind.
- **Mobilfunk-Datenlimit.** Für jede Mobilfunk-Schnittstelle mit aktiviertem
  Limit auf dem Router: genutzte Daten, Limit, genutzte Prozent, Reset-Zeit
  und ein Binärsensor **Datenlimit erreicht**. Gelesen von
  `/data_limit/status`; der Router zählt und erzwingt das Limit, die
  Integration zeigt es nur an. Der SIM-Slot kommt aus der
  Schnittstellenkonfiguration.
- **Schalter für Portweiterleitungen.** Ein Schalter pro Regel von
  `/firewall/port_forwards/config`, der die Regel ein- oder ausschaltet. Es
  wird nur das Feld `enabled` geschrieben, und die Einstellung wird nach der
  Änderung zurückgelesen, wie bei den Roaming-Schaltern.
- Die drei Seiten sind optional: Ein Router oder Benutzer ohne sie bekommt
  keine Entitäten dafür, und alles andere funktioniert weiter. Sie erscheinen
  im Debug-Bericht und in der Diagnose.
- Das Beispiel-Dashboard hat eine Failover-Pille für Mobilfunk, eine Pille für
  Portweiterleitungen und eine Pille für das Datenlimit. Sie blenden sich
  selbst aus, solange ihre Entitäten nicht existieren.
- Das Probe-Tool liest außerdem `/data_limit/status` und die Seiten zur
  monatlichen Datennutzung.

### Geändert

- Der Failover-Status und das Datenlimit werden höchstens alle zwei Minuten
  gelesen, wie die DHCP-Clients, um die Last auf schwachen Routern klein zu
  halten. Die Regeln der Portweiterleitungen sind Konfiguration und folgen
  dem Konfigurationsintervall.
- Doku: Der Router-Benutzer braucht Lesezugriff auf die neuen Seiten; die
  Schalter für Portweiterleitungen sind unter dem aufgeführt, was die
  Integration auf dem Router ändert.

## [0.9.1] - 2026-11-16

### Behoben

- Das Debug-Log und der Diagnose-Download zeigen keine MAC- oder IP-Adressen
  mehr, die als Schlüsselnamen in Router-Antworten vorkommen. Der WLAN-Status
  eines Radios listet seine verbundenen Geräte mit der MAC-Adresse als
  Schlüssel auf, und die Strukturansicht gab diese Schlüssel aus. Solche
  Schlüssel erscheinen jetzt als `<mac>` oder `<ip>` (ein Eintrag für die
  Struktur). Das Probe-Tool hat denselben Schutz. Ein Test mit einer
  MAC-Adresse in den Routerdaten prüft das.

## [0.9.0] - 2026-11-16

### Hinzugefügt

- **Debug-Protokollierung für den Support.** Mit „Debug-Protokollierung
  aktivieren“ auf der Integrationsseite zeigt das Log jetzt einen
  Router-Bericht (Modell, Firmware, welche Seiten geantwortet haben, fehlen
  oder langsam sind, Anzahl des Gefundenen), eine Zeile pro Anfrage (Methode,
  Pfad, HTTP-Status, Dauer und bei Änderungen die Namen der gesendeten Felder),
  die Struktur jeder Antwort einmal pro Seite (Schlüsselnamen und Typen), eine
  Zusammenfassungszeile pro Aktualisierung und die ausgeführten Aktionen. Es
  enthält keine Passwörter, Tokens, PINs, IMSI/IMEI/ICCID, Seriennummern,
  WLAN-Namen, Adressen oder Koordinaten; ein Test prüft das.
- Der Diagnose-Download listet auf, welche Router-Seiten funktionieren, fehlen
  oder langsam sind, und die Struktur jeder Antwort.
- GitHub-Issue-Vorlage, die nach Routermodell, Firmware, Debug-Log und
  Diagnose fragt.

### Geändert

- Verbindungsfehler ohne Text (Timeouts) sagen jetzt, was passiert ist, zum
  Beispiel „Cannot reach 192.168.1.1: TimeoutError“.
- Home Assistant schreibt die Router-Adresse nicht mehr in seine eigenen
  Logzeilen dieser Integration (der Name des Update-Koordinators nutzte sie).

### Geändert

- Doku: Die Daten-Roaming-Schalter sind auf einem RUTC50 in beide Richtungen
  bestätigt (verweigern und erlauben); der Router zeigte jedes Mal die neue
  Einstellung.

## [0.8.0] - 2026-11-16

### Hinzugefügt

- Schalter **Daten-Roaming SIM *Slot* erlauben** für jede SIM. Er zeigt und
  ändert die Router-Einstellung „Deny data roaming“ (an bedeutet, Roaming ist
  erlaubt). Es wird nur dieses eine Feld geschrieben, nie PIN oder APN, die
  Einstellung wird nach der Änderung zurückgelesen, und es wird ein Fehler
  angezeigt, wenn der Router sie nicht übernommen hat. Die Schalter erscheinen,
  wenn der Router die Seite mit den SIM-Einstellungen (`/sim_cards/config`)
  beantwortet.
- Das Beispiel-Dashboard hat zwei Pillen für das Roaming von SIM 1 und SIM 2:
  grün, wenn erlaubt, grau, wenn verweigert. Das Erlauben fragt nach einer
  Bestätigung.
- Die Konfigurationsseite `/sim_cards/config` wird mit den anderen selten
  geänderten Seiten gelesen.

### Hinweise

- Die Schreibanfrage folgt dem Muster der anderen Einstellungen, wurde aber
  noch nicht auf einem echten Router getestet. Probiere sie zuerst aus, indem
  du den Schalter einschaltest, während er schon an ist, was den Wert sendet,
  den er bereits hat.

## [0.7.0] - 2026-11-16

### Hinzugefügt

- Modemsensor **Netzregistrierung** (zum Beispiel „Registered, home“) und
  Binärsensor **Roaming**, an, solange die Registrierung Roaming sagt. Beide
  stammen aus dem bereits gelesenen Modemstatus, es gibt also keine neue
  Anfrage an den Router und keine Änderung an ihm.
- Das Beispiel-Dashboard hat eine Pille **Netzregistrierung**, die bei Roaming
  orange wird.
- `tools/probe_endpoints.py` liest außerdem die Modem-Konfigurationsseiten
  (genutzt, um nach der Roaming-Einstellung zu suchen).

### Geändert

- Doku gegen den Code geprüft und korrigiert: Optionsliste, Passwortregel für
  gesicherte Netze (mindestens 8 Zeichen), der Sensor „WLAN verbunden“, die
  Formulierung der GPS-Bestätigung, der Platzhalter für die WireGuard-Instanz
  im Beispiel-Dashboard und die Reihenfolge der Dashboard-Voraussetzungen.
- Doku: GPS-Kurs und Fix-Status auf einem RUTC50 (geparkt) geprüft: Beide
  Felder existieren, der Fix-Status ist `1` bei einem Fix, der Kurs ist 0,
  wenn geparkt. Werte während der Fahrt sind noch zu bestätigen.
- Doku aktualisiert: Quelle der Routeruhr, benötigte Integrationsversion für
  das Beispiel-Dashboard sowie das schonende Abfragen und die GPS-Filterung in
  der Funktionsliste.

## [0.6.1] - 2026-11-16

### Behoben

- Die GPS-Sensoren springen bei einer einzelnen Messung nicht mehr auf 0
  Satelliten und 500 m Genauigkeit. Der Empfänger eines RUTC50 meldet
  gelegentlich eine leere Messung zwischen normalen; bis zu drei leere
  Messungen in Folge werden ignoriert, und die letzten guten Werte bleiben.
  Ein längerer Verlust des Fixes wird weiterhin sichtbar. Das vermeidet falsche
  Zonenwechsel in Automationen.

## [0.6.0] - 2026-11-16

### Geändert

- **Deutlich schonenderes Abfragen.** Die Integration fragte den Router bisher
  alle 30 Sekunden gleichzeitig nach etwa 11 Seiten, was die CPU eines RUTC50
  auf 40 bis 100 % trieb, während der Router selbst im Ruhezustand 3 %
  anzeigte. Jetzt werden die Seiten nacheinander gelesen, die Statusseiten
  (Uplink, WLAN-Status, Modem, GPS, Last) bei jeder Aktualisierung und die
  Seiten, die sich selten ändern (WLAN-Konfiguration, Radios,
  WireGuard-Instanzen, Multi-AP-Liste), nur alle 5 Minuten. Die DHCP-Clients
  werden höchstens alle 2 Minuten gelesen, eine Seite, die nicht existiert,
  wird erst nach 5 Minuten wieder abgefragt. Aktionen der Integration lesen
  alles sofort neu.

### Hinzugefügt

- Neue Option **Konfigurationsintervall** (30 bis 3600 Sekunden, Standard 300)
  neben dem bestehenden **Aktualisierungsintervall**.

## [0.5.2] - 2026-11-16

### Behoben

- Solange die WLAN-Statusseite des Routers nicht antwortet, behaupten die
  WLAN-Sensoren nicht mehr „unknown“ oder „no Wi-Fi“: Trägt eine
  WLAN-Schnittstelle den Uplink, werden Name und Band des gespeicherten Netzes
  aus der Router-Konfiguration genommen, **WLAN verbunden** ist an, und der
  Hotspot-Status folgt der Internetprüfung. Signal und Verbindungsgeschwindigkeit
  bleiben unbekannt, bis die Seite antwortet.
- Beispiel-Dashboard: Das Uplink-Badge fällt auf den Uplink-Typ zurück, wenn
  der WLAN-Name unbekannt ist, und das Geschwindigkeits-Badge zeigt einen
  Strich statt „unknown Mbit/s“.

## [0.5.1] - 2026-11-16

### Behoben

- Eine langsame Router-Seite nimmt nicht mehr jede Entität offline. Zuvor ließ
  ein Timeout auf irgendeiner Seite (beobachtet beim WLAN-Status eines RUTC50)
  die gesamte Aktualisierung fehlschlagen und ließ alle Entitäten nicht
  verfügbar und die Einrichtung im Wiederholungsmodus. Jetzt ist nur die
  Schnittstellenliste unverzichtbar; jede andere Seite behält ihre letzten
  bekannten Werte, wenn sie nicht antwortet, wird nach zwei Minuten erneut
  abgefragt (damit ein angeschlagener Router nicht beschäftigt gehalten wird)
  und protokolliert eine Warnung.

### Geändert

- Beispiel-Dashboard: Das Hinzufügen eines WLAN-Netzes folgt jetzt drei
  Schritten. Nachdem du ein Netz gewählt hast, wird seine Pille mit einem
  grünen Rand hervorgehoben und bietet das optionale Passwort und
  **Hinzufügen**; davor wird ein grauer Hinweis angezeigt.

## [0.5.0] - 2026-11-16

### Hinzugefügt

- WireGuard-Steuerung: für jede WireGuard-Instanz ein Binärsensor für den
  Schnittstellenzustand, ein Schalter zum Aktivieren oder Deaktivieren, eine
  Schaltfläche **WireGuard neu verbinden** (aus, warten, an) und
  Verkehrszähler. Ohne das Recht, die Konfiguration zu lesen, wird ein Tunnel
  nur beobachtet, nicht geschaltet.
- Sensoren für den Routerzustand: Betriebszeit, CPU-Last, Speicherauslastung
  (die Flash-Auslastung ist standardmäßig deaktiviert) und **DHCP-Clients**
  mit einer Liste der verbundenen Geräte als Attribut (keine MAC-Adressen).
- Die Routeruhr stammt jetzt aus dem Systemauslastungsstatus, mit dem
  `Date`-Header als Rückfall.
- Alle neuen Endpunkte sind optional: Darf der Router-Benutzer eine Seite nicht
  lesen, werden die passenden Entitäten einfach nicht angelegt.
- Das Beispiel-Dashboard hat eine Pille **WireGuard-Tunnel neu starten** und
  einen Block **Routerzustand**. Doku: neuer Einrichtungsschritt 13,
  Berechtigungen, Fehlerbehebung.

### Behoben

- Der Diagnose-Download verbirgt jetzt den VPN-Prüf-Host und enthält den
  VPN-Status.

### Geändert

- Doku: Die VPN-Prüfung warnt davor, den WireGuard-Endpunkt und seinen
  UDP-Port als Ziel zu verwenden.
- `tools/probe_endpoints.py` ist eigenständig: Es braucht nur `aiohttp`, nicht
  Home Assistant.

### Geändert

- Doku: Schritt-für-Schritt-Anleitung für die optionale VPN-Prüfung
  (Erste Schritte, Schritt 12), Zeilen zur Fehlerbehebung, bekannte
  Einschränkungen und die Ideen zu WireGuard-Handshake und Neuverbinden unter
  Geplant.

## [0.4.0] - 2026-11-16

### Hinzugefügt

- VPN-Prüfung: Gib in den Optionen einen DNS-Namen, eine IPv4- oder
  IPv6-Adresse (und einen TCP-Port) eines Geräts hinter einem
  Site-to-Site-Tunnel ein. Der neue Binärsensor **VPN erreichbar** und der
  Sensor **VPN-Latenz** zeigen, ob der Tunnel Verkehr trägt. Es funktioniert
  mit jedem VPN-Typ. Eine abgelehnte Verbindung zählt als erreichbar. Das
  Beispiel-Dashboard hat eine VPN-Pille, die nur erscheint, wenn die Prüfung
  eingerichtet ist.
- `tools/probe_endpoints.py`: eine schreibgeschützte Probe, die auflistet,
  welche weiteren REST-Endpunkte (VPN, Firmware, DHCP, Failover und andere)
  ein Router anbietet. Sie gibt Namen und Typen aus, nie Schlüssel, Adressen
  oder andere Textwerte.

### Geändert

- Das Beispiel-Dashboard `dashboards/teltonika-control.yaml` hat ein neues
  Aussehen: farbige Bubble-Card-Pillen in zwei Spalten und Mushroom-Badges
  oben. WLAN zuerst und Mobilfunk zuerst sind zwei Schaltflächen, die die
  aktive Priorität anzeigen, das Prioritäts-Dropdown entfällt. Bubble Card
  (und optional Mushroom) wird nur für dieses Dashboard gebraucht, nicht für
  die Integration.
- Die Doku stellt klar, dass keine Home-Assistant-Helfer nötig sind, und
  ergänzt eine Schritt-für-Schritt-Anleitung für einen optionalen monatlichen
  Datenzähler mit dem Helfer Utility Meter.

## [0.3.1] - 2026-11-16

### Geändert

- Neue Markenbilder: ein Router mit Antennen, WLAN-Bögen und dem Text RUTx als
  Icon, dazu ein Logo mit dem Namen in einer hellen und einer dunklen
  Variante. Das Artwork ist original und wird von `tools/make_brand_images.py`
  gezeichnet.
- Die README stellt klar, dass das Projekt nicht mit Teltonika Networks
  verbunden ist, und beschreibt, wie man die Tests unter Linux oder WSL
  ausführt.

## [0.3.0] - 2026-11-16

### Hinzugefügt

- Native Entitäten zur WLAN-Verwaltung: die Schaltflächen **WLANs suchen**,
  **Ausgewähltes WLAN hinzufügen** und **Ausgewähltes WLAN entfernen**, die
  Auswahlen **Gefundene WLANs** und **Gespeicherte WLANs**, eine Text-Entität
  **WLAN-Passwort** (zeigt nur eine Maske) und ein Sensor **Letzte
  WLAN-Aktion**. Gespeicherte Netze enthalten die Multi-AP-Liste.
- Diagnosesensor **Routerzeit** aus dem `Date`-Header der Router-Antworten
  (standardmäßig deaktiviert, nur wenn der Header vorhanden ist).
- Fertiges Dashboard: Bereiche zum Hinzufügen und Entfernen von WLAN-Netzen und
  für GPS. Anleitungen aktualisiert.
- `tools/live_smoke_test.py` gibt die Feldnamen des Gerätestatus, der
  GPS-Antwort und der Routeruhr aus.

### Behoben

- Die WLAN-Sensoren (Netz, Signal, Band, Geschwindigkeit) beschreiben jetzt die
  Verbindung, die den Uplink trägt. Zuvor wurde der erste verbundene Eintrag
  gezeigt, was falsch war, wenn der Router zweimal mit demselben Netz
  verbunden war.

## [0.2.0] - 2026-11-16

### Hinzugefügt

- Config Flow mit erneuter Anmeldung, Neukonfiguration und Optionen.
- Sensoren für Uplink, WLAN-Client, Hotspot-Anmeldestatus und Modemsignal.
- Binärsensoren für WLAN, Internet, Hotspot-Anmeldung und Mobilfunkdaten.
- Schalter für die eigenen Access Points des Routers mit dem echten
  Ein/Aus-Zustand.
- Schaltflächen zum Neustart der Mobilfunkdaten, zum Neuverbinden des WLANs und
  zum Neustart des Routers.
- Auswahlen für die Uplink-Priorität und den SIM-Slot von Dual-SIM-Modems.
- Dienste, um auf eine Hotspot-Anmeldung zu warten, die Priorität zu setzen und
  WLAN-Netze zu verwalten.
- Diagnose ohne personenbezogene Daten.
- Englische und deutsche Übersetzungen.
- Schritt-für-Schritt-Anleitung in `docs/getting-started.de.md`.
- Fertiges Dashboard in `dashboards/teltonika-control.yaml` mit einer
  Anleitung in `docs/dashboard.de.md`.
- GPS: ein Device-Tracker für die Position und Sensoren für Geschwindigkeit,
  Höhe, Satelliten, Genauigkeit, Kurs und Fix-Status, nur bei Routern mit GPS.
- Dienste akzeptieren ein Dienstziel: das Router-Gerät oder jede Entität des
  Routers (auch eine Modem-Entität). `device_id` in den Daten funktioniert
  weiterhin.
- `join_wifi` speichert Netze eines Multi-AP-Radios (5 GHz beim RUTC50) in der
  Multi-AP-Liste und weist ein Radio ab, das bereits einen Client oder Multi AP
  hat.
- `forget_wifi` entfernt Multi-AP-Listeneinträge über `ssid` (nie den letzten)
  und entfernt die Schnittstelle eines vergessenen Clients, sofern sie keine
  Standardschnittstelle ist.
