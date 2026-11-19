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
1. Im Dialog auf **DHL Login öffnen** klicken – am besten in **Chrome am PC**.
2. **Vor** dem Login die Entwicklertools öffnen (F12, Reiter *Konsole*).
3. Mit DHL-Konto anmelden (ggf. SMS/E-Mail-Code).
4. Die Weiterleitung schlägt fehl – in der Konsole steht ein Link
   `dhllogin://de.deutschepost.dhl/login?code=…`. Komplett kopieren und **sofort** einfügen
   (der Code ist nur kurz gültig).

Danach hält sich die Integration per Refresh-Token selbst angemeldet. Läuft der Token doch
ab, meldet Home Assistant „Neu authentifizieren“ – dann die Schritte wiederholen.

Für die Briefankündigung muss sie in deinem DHL-/Post-Konto aktiviert sein.

## Entitäten
| Entität | Inhalt |
|---|---|
| `sensor.dhl_pakete_unterwegs` | Anzahl nicht zugestellter Sendungen, Liste im Attribut `parcels` |
| `sensor.dhl_pakete_in_zustellung` | Pakete „in Zustellung“ (mit Zeitfenster/Stopps, falls vorhanden) |
| `sensor.dhl_briefankundigung` | Anzahl angekündigter Briefe, Attribut `letters` |
| `image.dhl_brief_1` … `_10` | entschlüsselte Scans der Briefe (1–3 standardmäßig aktiv) |
| `sensor.dhl_alle_sendungen` | alle nicht archivierten Sendungen (standardmäßig deaktiviert) |

Abfrageintervall: Optionen der Integration (Standard 30 min, min. 10 min).

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
