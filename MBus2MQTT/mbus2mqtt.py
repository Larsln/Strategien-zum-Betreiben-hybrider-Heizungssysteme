"""
M-Bus to MQTT Gateway
---------------------
Dieses Skript liest Daten von M-Bus-Zählern über eine serielle Schnittstelle aus,
interpretiert die XML-Antworten und veröffentlicht die extrahierten Werte 
(Energie, Temperatur, Leistung, Volumen) als JSON-Strings via MQTT.

Abhängigkeiten:
    - mbus-serial-request-data (CLI-Tool im Pfad)
    - paho-mqtt (Python Library)

Umgebungsvariablen:
    MBUS_SERIAL: Pfad zum seriellen Gerät (Standard: /dev/ttyAMA4)
    MBUS_BAUD:   Baudrate für M-Bus (Standard: 2400)
    MBUS_ADDRS:  Kommagetrennte Liste der Primäradressen (z.B. "1,2,3")
    MQTT_HOST:   Hostname des MQTT Brokers (Standard: mosquitto)
    INTERVAL:    Sekunden pro vollständigem Abfrage-Zyklus
"""


import os, time, json, subprocess, xml.etree.ElementTree as ET
import paho.mqtt.client as mqtt

SERIAL   = os.getenv("MBUS_SERIAL", "/dev/ttyAMA4")
BAUD     = os.getenv("MBUS_BAUD", "2400")
ADDRS    = [a.strip() for a in os.getenv("MBUS_ADDRS", os.getenv("MBUS_ADDR","1")).split(",") if a.strip()]
MQTT_HOST= os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT= int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER= os.getenv("MQTT_USER", "")
MQTT_PASS= os.getenv("MQTT_PASS", "")
INTERVAL = int(os.getenv("INTERVAL", "30"))  # Gesamtintervall pro vollständigem Durchlauf

def publish(client, topic, payload):
   """
    Veröffentlicht eine Nachricht auf dem MQTT-Broker.
    
    Args:
        client: Der paho-mqtt Client.
        topic: Das Ziel-Topic.
        payload: Die zu sendenden Daten (String oder JSON).
    """
   client.publish(topic, payload, qos=0, retain=True)


def read_xml(addr: str) -> str:
  """
    Ruft M-Bus Daten für eine Adresse via 'mbus-serial-request-data' ab.
    
    Args:
        addr: Die Primäradresse des M-Bus Zählers.
        
    Returns:
        Die XML-Antwort des CLI-Tools als String.
        
    Raises:
        subprocess.CalledProcessError: Wenn der Aufruf fehlschlägt.
    """
  cmd = ["mbus-serial-request-data","-b",BAUD, SERIAL, str(addr)]
  return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)


def parse(xml_text: str) -> dict:
    """
    Extrahiert physikalische Werte aus der M-Bus XML-Antwort.
    
    Es werden nur Momentanwerte (StorageNumber 0/-) berücksichtigt.
    Unterstützte Einheiten: Energie (kWh/MWh), Temperatur (°C), 
    Leistung (kW), Volumenstrom (l/h) und Volumen (l/m³).
    
    Args:
        xml_text: Die vom Zähler empfangene XML-Struktur.
        
    Returns:
        Ein Dictionary mit den gemappten Werten (z.B. {'energy_kwh': 123.4}).
    """    
    data = {}
    root = ET.fromstring(xml_text)

    def norm(s: str) -> str:
        # Klein + Whitespace normalisieren (z. B. "1e-2  m^3")
        return " ".join((s or "").lower().split())

    for rec in root.findall(".//DataRecord"):
        unit_raw = rec.findtext("Unit") or ""
        unit = norm(unit_raw)
        val_s = rec.findtext("Value")
        if val_s is None:
            continue
        try:
            val = float(val_s)
        except:
            continue

        func = norm(rec.findtext("Function") or "")
        storage = (rec.findtext("StorageNumber") or "-").strip()

        # Nur Momentanwerte; fehlendes Storage ("-") wie 0 behandeln
        is_current = (storage in ("0", "-", "")) and ("instantaneous" in func or func in ("", "-"))
        if not is_current:
            continue

        # --- Energy ---
        if unit.startswith("energy"):
            if "(100 wh)" in unit:
                data["energy_kwh"] = val * 0.1
            elif "(kwh)" in unit or "(mwh)" in unit:
                # kWh direkt; MWh optional (falls je nach Zählerkonfig)
                if "(mwh)" in unit:
                    data["energy_kwh"] = val * 1000.0
                else:
                    data["energy_kwh"] = val

        # --- Temperatures ---
        elif "flow temperature" in unit:
            data["temp_flow_c"] = val / 100.0
        elif "return temperature" in unit:
            data["temp_return_c"] = val / 100.0
        elif "temperature difference" in unit:
            data["delta_t_c"] = val / 100.0

        # --- Power ---
        elif unit.startswith("power"):
            # "Power (100 W)" -> kW
            data["power_kw"] = val * 0.1

        # --- Volume flow ---
        elif "volume flow" in unit:
            # "(m m^3/h)" ist m³/h → in Liter/h
            data["flow_lh"] = val

        # --- Volume (nur EINEN nehmen – bevorzugt 'm m^3', sonst '1e-2 m^3') ---
        elif unit.startswith("volume"):
            # noch keinen Volumenwert gesetzt?
            if "volume_l" not in data:
                if "volume (m m^3)" in unit:
                    # m³
                    data["volume_m3"] = val / 1000
                    data["volume_l"] = val
                elif "volume (1e-2 m^3)" in unit:
                    # Hundertstel m³
                    data["volume_m3"] = val / 100.0
                    data["volume_l"]  = val * 10.0

    return data

def main():
  """
    Hauptschleife: Initialisiert den MQTT-Client und fragt zyklisch alle
    konfigurierten M-Bus Adressen ab.
    """
  client = mqtt.Client()
  if MQTT_USER: client.username_pw_set(MQTT_USER, MQTT_PASS)
  client.connect(MQTT_HOST, MQTT_PORT, 60)

  # kleine Pause pro Zähler, damit Gesamtzyklus ~INTERVAL Sekunden hat
  pause = max(1, INTERVAL // max(1, len(ADDRS)))

  while True:
    for addr in ADDRS:
      base = f"mbus/{addr}"
      try:
        xml_text = read_xml(addr)
        data = parse(xml_text)
        if data:
#          for k, v in data.items():
#            publish(client, f"{base}/{k}", v)
          publish(client, f"{base}/state", json.dumps(data, separators=(",",":")))
        else:
          publish(client, f"{base}/error", "no_data_parsed")
      except Exception as e:
        publish(client, f"{base}/error", str(e))
      time.sleep(pause)

if __name__ == "__main__":
  main()

