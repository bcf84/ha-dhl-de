# DHL Deutschland für Home Assistant

Pakete aus deinem DHL-Konto + Briefankündigung der Deutschen Post (inkl. Briefbilder) –
Portierung des DHL-Teils von [ioBroker.parcel](https://github.com/TA2k/ioBroker.parcel) (MIT).

Inoffiziell: nutzt dieselbe Schnittstelle wie die DHL-App. Kann brechen, wenn DHL etwas ändert.

## Installation
1. Marketplace/HACS → Benutzerdefiniertes Repository `bcf84/ha-dhl-de` (Typ *Integration*) hinzufügen und herunterladen –
   oder den Ordner `custom_components/dhl_de` nach `/config/custom_components/dhl_de` kopieren.
2. Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → **DHL Deutschland**.

## Login (einmalig)
Am PC (am Handy fehlt die Konsole):
1. Im Dialog **F12** drücken, dann auf den Login-Link klicken und bei DHL anmelden.
2. In der Konsole die **rote Zeile** mit `dhllogin://` kopieren (gern die ganze Zeile).
3. Sofort im Dialog einfügen – der Code ist nur kurz gültig.

Danach hält sich die Integration per Refresh-Token selbst angemeldet. Läuft der Token doch
ab, meldet Home Assistant „Neu authentifizieren“ – dann die Schritte wiederholen.

Für die Briefankündigung muss sie in deinem DHL-/Post-Konto aktiviert sein.

## Entitäten
| Entität | Inhalt |
|---|---|
| `sensor.dhl_pakete_unterwegs` | Anzahl nicht zugestellter Sendungen, Liste im Attribut `parcels` |
| `sensor.dhl_pakete_in_zustellung` | Pakete „in Zustellung“ (mit Zeitfenster/Stopps, falls vorhanden) |
| `sensor.dhl_pakete_abholbereit` | Pakete, die in Packstation/Filiale liegen, mit `pickup_location` |
| `sensor.dhl_briefankundigung` | Anzahl angekündigter Briefe, Attribut `letters` |
| `image.dhl_brief_1` … `_10` | entschlüsselte Scans der Briefe (1–3 standardmäßig aktiv) |
| `sensor.dhl_paket_<name>` | **ein Sensor pro Paket**, automatisch angelegt und wieder entfernt, sobald DHL die Sendung archiviert. Zustand = DHL-Status, Details als Attribute |
| `sensor.dhl_alle_sendungen` | alle nicht archivierten Sendungen (standardmäßig deaktiviert) |

Abfrageintervall: Optionen der Integration (Standard 30 min, min. 10 min).

## Paketliste im Dashboard (mit auto-entities)
```yaml
type: custom:auto-entities
card:
  type: entities
  title: DHL Pakete
filter:
  include:
    - attributes:
        integration: dhl_de
      entity_id: sensor.dhl_paket_*
show_empty: false
```

## Beispiel: Benachrichtigung bei Paket in Zustellung
```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.dhl_pakete_in_zustellung
    above: 0
actions:
  - action: notify.notify
    data:
      message: >
        DHL kommt heute:
        {% for p in state_attr('sensor.dhl_pakete_in_zustellung','parcels') %}
        {{ p.name }} {{ p.delivery_window | default('') }}
        {% endfor %}
```
