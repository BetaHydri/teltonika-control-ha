# Best Practices

[English](best-practices.md) | **Deutsch**

Kurze Regeln, die deinen Router sicher und dein Home-Assistant-Setup
aufgeräumt halten. Jede Regel verlinkt auf die Stelle in der Dokumentation, die
sie erklärt.

<a id="router-access"></a>

## Zugriff auf den Router

- **Nutze einen eigenen Router-Benutzer** für Home Assistant, nicht `admin`.
  Fang nur mit Leserechten an und ergänze Schreibrechte für die Seiten, die du
  brauchst. Siehe
  [Router-Benutzer und Berechtigungen](../README.de.md#router-user-and-permissions).
- **Öffne die Weboberfläche des Routers nicht zum Internet**, nur damit Home
  Assistant sie erreicht. Greife über das LAN oder ein VPN darauf zu.
- **Lass SSH aus** für den Home-Assistant-Benutzer. Die Integration nutzt es
  nicht.

<a id="firewall-switches"></a>

## Firewall-Switches

- **Schalte eine Portweiterleitung oder Verkehrsregel nur ein, solange du sie
  brauchst**, zum Beispiel die HTTP-Weiterleitung für eine
  Zertifikatserneuerung. Eine Regel, die an ist, lässt Verkehr aus dem Internet
  an deinen Router oder an ein Gerät dahinter.
- **Schalte niemals die Regel aus, die deinen eigenen Fernzugriff trägt.**
  Erreichst du Home Assistant über einen weitergeleiteten Port, sperrt dich das
  Ausschalten dieser Regel aus. Prüfe den Port, bevor du tippst.
- **Behalte die Zähler im Blick**, *Offene Portweiterleitungen* und
  *Firewall-Regeln zum Internet offen*, oder nutze das
  [Firewall-Dashboard](firewall-dashboard.de.md), um zu sehen, was gerade offen
  ist.
- **Lass den Router die Regeln anlegen.** Die Integration schaltet vorhandene
  Regeln nur ein oder aus; lege sie einmal in der Weboberfläche des Routers an
  und lass sie standardmäßig ausgeschaltet.

<a id="uplink-and-hotspots"></a>

## Uplink und Hotspots

- **Speichere jedes WLAN, das du nutzt, als Client-Netz** am Router. Ohne eines
  ist die Auswahl der Priorität nicht verfügbar.
- **Nutze *WLAN zuerst* nur mit einem Rückfall**: einer Automatisierung, die auf
  Mobilfunkdaten zurückgeht, wenn der Internettest fehlschlägt, siehe
  [Automatisierungsbeispiele](automation-examples.de.md#back-to-mobile-data-when-the-wi-fi-has-no-internet).
- **Setze die URL für den Internettest** (der Standard antwortet mit HTTP 204).
  Die Erkennung der Hotspot-Anmeldung und der Rückfall hängen davon ab. Der Test
  ist nur sinnvoll, wenn Home Assistant das Internet über diesen Router
  erreicht.
- **Rechne mit einer kurzen Unterbrechung**, wenn du die SIM wechselst oder die
  Mobilfunkverbindung neu startest. Mach das aus einer Automatisierung nur mit
  einer Bedingung, die sagt, dass es sicher ist.

<a id="mobile-data"></a>

## Mobile Daten

- **Lass das Datenlimit des Routers aktiviert.** Es übernimmt das Zählen. Setze
  es auf oder über dein Vertragsvolumen, weil der Router die Mobilfunkdaten am
  Limit abschaltet, solange sein Ratenlimit nicht aktiv ist.
- **Trage dein Vertragsvolumen als *Mobilfunk-Datenvolumen (GB)* ein** in den
  Optionen. Der Prozentwert und die Warnungen folgen dann deinem Vertrag, nicht
  dem Limit des Routers. Siehe
  [Mobilfunk-Datenlimit](../README.de.md#mobile-data-limit).
- **Warne aus Home Assistant**, zum Beispiel bei 80 % und 95 %, statt dich auf
  die SMS des Routers zu verlassen. Siehe die
  [fertige Automatisierung](automation-examples.de.md#mobile-data-volume-warning).
- **Achte auf die Einheiten**: Der Router zählt in MB zu 1.048.576 Byte, Home
  Assistant zeigt GB zu 10⁹ Byte. Provider nutzen Letzteres.

<a id="automations"></a>

## Automatisierungen

- **Nutze die Entitäten, nicht die Router-API.** Alles ist eine Entität des
  Router-Geräts; es braucht keine Helfer, Skripte oder YAML-Pakete.
- **Bevorzuge native Trigger**: `state` mit `for:` für Ausfälle
  (Hotspot-Anmeldung, WLAN verloren, VPN down), `numeric_state` für
  Schwellenwerte. Ein `for:` von zwei bis drei Minuten vermeidet Fehlalarme,
  während der Router sich neu verbindet.
- **Ignoriere `unknown` und `unavailable`** in Änderungs-Triggern, damit ein
  Router-Neustart oder ein Neustart von Home Assistant keine Benachrichtigung
  sendet.
- **Nutze einen Benachrichtigungs-`tag`** und lösche die Meldung, wenn das
  Problem weg ist, damit sich alte Warnungen nicht anhäufen.
- **Wähle den Modus der Automatisierung bewusst**: `restart` für Timeouts,
  `queued` für Nachrichten, die alle ankommen müssen, `single` für Einmal-Aktionen.
- **Nutze `entity_id`, niemals `device_id`**, damit ein neu hinzugefügter Router
  deine Automatisierungen nicht kaputt macht.

<a id="performance"></a>

## Performance

- **Behalte die Standardintervalle** (30 s Status, 300 s Konfiguration). Einige
  RUT(x)-Modelle haben eine schwache CPU. Wirkt der Router langsam, erhöhe
  beide und beobachte den Sensor **CPU-Last**. Siehe
  [Optionen](../README.de.md#options).
- **Betreibe keine anderen Werkzeuge, die den Router gleichzeitig abfragen**,
  etwa eine zweite Integration oder ein Skript mit eigener Anmeldung, wenn du
  Anmeldefehler siehst. RutOS kann eine Adresse nach wiederholten
  fehlgeschlagenen Anmeldungen sperren.

<a id="dashboards"></a>

## Dashboards

- **Ersetze den Platzhalter** in den Beispiel-Dashboards durch dein
  Entitäts-Präfix und prüfe das Ergebnis, bevor du speicherst.
- **Verberge private Daten** (Karte, Telefonnummer, weitergeleitete Ports),
  bevor du einen Screenshot teilst.
- **Starte mit dem Beispiel und kürze dann.** Entferne Pills für Hardware, die
  du nicht hast, etwa eine zweite SIM oder WLAN.

<a id="when-something-is-wrong"></a>

## Wenn etwas nicht stimmt

- Schalte das [Debug-Logging](../README.de.md#debug-logging) ein und lade die
  Diagnose herunter. Beide schwärzen das Passwort.
- Prüfe zuerst die [bekannten Einschränkungen](../README.de.md#known-limitations).
  Feldnamen unterscheiden sich leicht zwischen RutOS-Releases, deshalb lohnt
  sich bei einer leeren Entität oft ein Issue mit angehängter Diagnose.
