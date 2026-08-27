# Data format

CSV telemetry accepts common aliases: `alt` / `altitude`, `temp` / `temperature`, `volt` / `battery_voltage`, `gps_lat`, `gps_lon`, `time`, and `packet`. Canonical names include `packet_number`, `timestamp_s`, `altitude_m`, `velocity_m_s`, `pressure_hpa`, `temperature_c`, `battery_v`, `latitude`, `longitude`, `phase`, and `gps_valid`.

Rows with invalid values, impossible ranges, duplicate packet numbers, or out-of-order packets are rejected and reported with their row numbers. Imported source content is not modified. The Files view shows a mapping preview first; only a confirmed import becomes a persisted `Flight` and its `TelemetryPacket` rows. Each flight stores source hash, mapping, validation issues, and reusable statistics.
