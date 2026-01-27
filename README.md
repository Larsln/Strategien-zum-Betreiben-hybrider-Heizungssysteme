# Strategien zum Betreiben hybrider Heizungssysteme

Dieses Repository beinhaltet die Software-Infrastruktur für die Bachelorarbeit **"Strategien zum Betreiben hybrider Heizungssysteme?"**.

## 🎯 Projektziel

Das primäre Ziel des Projekts ist die Entwicklung einer innovativen Betriebsstrategie für ein hybrides Heizungssystem (Wärmepumpe + Gasbrennwerttherme) in einem Einfamilienhaus. Durch den Einsatz intelligenter Regelungstechnik soll die Effizienz des Wärmeerzeugermanagements von einem Standardniveau (Klasse C) auf ein gehobenes Level (Klasse B) nach **DIN EN ISO 52120-1** angehoben werden.

Kernstück der Regelung ist eine **prädiktive Steuerung**, die mittels eines **k-Nearest-Neighbors (k-NN) Algorithmus** den Coefficient of Performance (COP) der Wärmepumpe prognostiziert. Basierend auf aktuellen Energiepreisen und dem prognostizierten Wirkungsgrad entscheidet das System dynamisch und vollautomatisch über den ökonomisch sinnvollsten Wärmeerzeuger (bivalent-alternativer Betrieb).

## 🏗 Systemarchitektur

Das System basiert auf einer containerisierten Architektur auf einem Raspberry Pi. **Home Assistant** fungiert als zentrale Datendrehscheibe und Logik-Instanz, während **InfluxDB** für die Zeitreihenspeicherung und komplexe Berechnungen (k-NN) zuständig ist.

Der Software-Stack umfasst folgende Docker-Container:

- **Home Assistant:** Zentrale Steuerung, Integration der Sensorik (GPIO, Shelly) und Ausführung der Automatisierungslogik.
- **Mosquitto (MQTT):** Message Broker zur Kommunikation zwischen den Diensten.
- **M-Bus Gateway:** Ein Python-basiertes Script (`mbus2mqtt`), das Daten der Wärmemengenzähler via `libmbus` ausliest und an MQTT sendet.
- **InfluxDB:** Persistierung der Sensordaten und Ausführung der Prognose-Tasks mittels Flux.
- **Grafana:** Visualisierung der Systemzustände, Verbrauchsanalysen und Monitoring der Bivalenzpunkte.

Die Fernwartung wird über **Tailscale** realisiert.

## 📂 Repository Struktur

Die Repository-Struktur ist nach Diensten (Container/Subsysteme) gegliedert. Jeder Ordner enthält die zugehörige Docker-Compose-Datei sowie die service-spezifischen Konfigurationen, Skripte und Export-Dateien.

```text
.
├── Grafana/
│   ├── docker-compose-grafana.yaml      # Grafana-Container (Visualisierung)
│   └── Leistungsdashboard.json          # Dashboard-Export (JSON)
├── Home Assistant/
│   ├── docker-compose-home-assistant.yaml   # Home-Assistant-Container
│   ├── configuration.yaml                   # Hauptkonfiguration
│   ├── benutzereinstellungen.yaml           # UI/Benutzeroberfläche
│   ├── parameter_fuer_fachkraefte.yaml      # UI/Fachkraftoberfläche
│   └── heizlogik.yaml                       # zentrale Steuerungslogik (Automationen/Logik)
├── InfluxDB/
│   ├── docker-compose-influxdb.yaml     # InfluxDB-Container
│   ├── cop_calculation.flux             # Task: IST-COP Berechnung
│   └── cop_prognose.flux                # Task: COP-Prognose (k-NN)
└── MBus2MQTT/
    ├── docker-compose-mbus2mqtt.yaml    # M-Bus->MQTT Service (Container)
    ├── Dockerfile-mbus2mqtt             # Image-Build für den M-Bus-Adapter
    └── mbus2mqtt.py                     # Python-Skript: M-Bus auslesen & nach MQTT publishen
```

## 🖥 Hardwarekomponenten

### Zentrale Recheneinheit & Speicher
- **1× Raspberry Pi 4 Model B**
- **1× SD-Karte (64 GB)** – Bootmedium
- **1× USB 3.0 SSD (256 GB)** – Datenhaltung (InfluxDB, Logs)

### Stromversorgung
- **1× 5V Netzteil** – Versorgung des Raspberry Pi
- **1× 12V Netzteil** – Versorgung des M-Bus

### Schnittstellen & Aktoren
- **1× Zihatec M-Bus HAT** – M-Bus Master für Wärmemengenzähler
- **2× 3,3V Relaismodule** – Ansteuerung der Freigabekontakte
  - Gasbrennwerttherme (Sperrkontakt)
  - Wärmepumpe (EVU-Kontakt)

### Sensorik
- **6× DS18B20 Temperaturfühler** – Vorlauf-, Rücklauf-, Pufferspeicher- und Außentemperaturmessungen
- **Twisted-Pair-Kabel** – 1-Wire- und M-Bus-Verdrahtung

### Wärmemengen- & Durchflussmessung
- **2× Kamstrup MULTICAL 603 für Wasser**
  - Zähler: `KAM-MC603-G54-3,5-260`
  - Kommunikationsmodul: `KAM-MC-COM-MBUS-PULSIN`

- **1× Kamstrup MULTICAL 603 für Solarflüssigkeit**
  - Zähler: `KAM-MC603-M`
  - Durchflussmesser: `DHM-DHM1400-G54-6,3-260-PULS`
  - Kommunikationsmodul: `KAM-MC-COM-MBUS-PULSIN`


---

Entwickelt im Rahmen der Bachelorarbeit an der FH Aachen.

