import "math"
import "array"

// Task-Konfiguration: Berechnung alle 5 Minuten
option task = {name: "wp_cop_prognose", cron: "*/5 * * * *"}

// 1. AKTUELLE REFERENZWERTE
currOutData =
    from(bucket: "home_assistant_bucket")
        |> range(start: -1d)
        |> filter(fn: (r) => r["entity_id"] == "thermometer_aussen" and r["_field"] == "value")
        |> last()
        |> findRecord(fn: (key) => true, idx: 0)

currBufData =
    from(bucket: "home_assistant_bucket")
        |> range(start: -1d)
        |> filter(
            fn: (r) => r["entity_id"] == "thermometer_pufferspeicher_h4" and r["_field"] == "value",
        )
        |> last()
        |> findRecord(fn: (key) => true, idx: 0)

cOut = float(v: currOutData._value)
cBuf = float(v: currBufData._value)

// 2. HISTORISCHE DATENBASIS
historicalData =
    from(bucket: "home_assistant_bucket")
        |> range(start: -1y, stop: -10m)
        |> filter(
            fn: (r) =>
                r["entity_id"] == "influx_wp_cop" or r["entity_id"] == "wp_relais"
                    or
                    r["entity_id"] == "thermometer_aussen" or r["entity_id"]
                    ==
                    "thermometer_pufferspeicher_h4",
        )
        |> filter(fn: (r) => r["_field"] == "value")
        // MAPPING: Umbenennen der IDs, damit sie keine Punkte mehr enthalten
        // SYNCHRONISATION: Alle Sensoren in ein 5-Minuten-Raster bringen
        |> aggregateWindow(every: 5m, fn: last, createEmpty: true)
        // LÜCKENFÜLLUNG (LOCF)
        |> fill(column: "_value", usePrevious: true)
        |> group()
        // TRANSFORMATION: Spalten für die Berechnung bauen
        |> pivot(rowKey: ["_time"], columnKey: ["entity_id"], valueColumn: "_value")
        // VALIDIERUNG: Nur Zeilen behalten, in denen alle 4 Werte vorhanden sind
        |> filter(
            fn: (r) =>
                exists r.wp_relais and exists r.thermometer_aussen
                    and
                    exists r.thermometer_pufferspeicher_h4,
        )
        // BETRIEBS-FILTER: Nur WP-Betrieb (Relais=1) und plausibler COP
        |> filter(
            fn: (r) => int(v: r.wp_relais) >= 1 and r.influx_wp_cop > 1 and r.influx_wp_cop < 8,
        )

// 3. k-NN BERECHNUNG
historicalData
    |> map(
        fn: (r) =>
            ({
                _time: r._time,
                cop_val: float(v: r.influx_wp_cop),
                dist:
                    math.sqrt(
                        x:
                            math.pow(x: float(v: r.thermometer_aussen) - float(v: cOut), y: 2.0)
                                +
                                math.pow(
                                    x: float(v: r.thermometer_pufferspeicher_h4) - float(v: cBuf),
                                    y: 2.0,
                                ),
                    ),
            }),
    )
    |> sort(columns: ["dist"], desc: false)
    |> limit(n: 3)
    |> mean(column: "cop_val")
    |> map(
        fn: (r) =>
            ({
                _time: now(),
                _measurement: "cop_prognose",
                _field: "value",
                _value: r.cop_val,
                entity_id: "influx_wp_cop_prognose",
            }),
    )
    |> to(bucket: "home_assistant_bucket", org: "home_assistant", tagColumns: ["entity_id"])
