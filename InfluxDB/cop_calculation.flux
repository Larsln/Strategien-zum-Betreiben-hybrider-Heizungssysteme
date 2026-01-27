import "math"

// Task-Konfiguration
option task = {name: "cop_calcultation", cron: "* * * * *"}

// 1. DATENAKQUISE & SYNCHRONISATION
data =
    from(bucket: "home_assistant_bucket")
        |> range(start: -1h)
        |> filter(
            fn: (r) =>
                (r["entity_id"] == "shelly_wp_power" or r["entity_id"] == "wmz_wp_power")
                    and
                    r["_field"] == "value",
        )
        // Mittelwertbildung für jede Minute
        |> aggregateWindow(every: 1m, fn: mean, createEmpty: true)
        // Lücken füllen (LOCF)
        |> fill(column: "_value", usePrevious: true)
        // Pivotierung: Macht aus den Zeilen Spalten (hier verschwindet "_value")
        |> pivot(rowKey: ["_time"], columnKey: ["entity_id"], valueColumn: "_value")
        // Letzte Zeile der Tabelle
        |> tail(n: 1)

// 2. BERECHNUNGSLOGIK
data
    |> map(
        fn: (r) => {
            // Sicherstellung der Datentypen und Existenzprüfung
            p_el = if exists r.shelly_wp_power then float(v: r.shelly_wp_power) else 0.0
            q_th = if exists r.wmz_wp_power then float(v: r.wmz_wp_power) else 0.0

            // Berechnung mit Guard Clause (kW-Bereich: 0.01 = 10W)
            calculated_cop = if p_el > 0.01 then q_th / p_el else 0.0

            return {
                _time: r._time,
                _value: float(v: calculated_cop),
                _field: "value",
                _measurement: "cop",
                entity_id: "influx_wp_cop",
            }
        },
    )
    // 3. SPEICHERN
    |> to(bucket: "home_assistant_bucket", org: "home_assistant", tagColumns: ["entity_id"])
