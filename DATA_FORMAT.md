# Data format

CSV telemetry accepts common aliases: `alt` / `altitude`, `temp` / `temperature`, `volt` / `battery_voltage`, `gps_lat`, `gps_lon`, `time`, and `packet`. Canonical names include `packet_number`, `timestamp_s`, `altitude_m`, `velocity_m_s`, `pressure_hpa`, `temperature_c`, `battery_v`, `latitude`, `longitude`, `phase`, and `gps_valid`.

Rows with invalid values, impossible ranges, or unknown mission phases are rejected and reported with their row numbers. Imported source content is not modified. Ambiguous columns require user confirmation in a future mapping step; this prototype only applies known unambiguous aliases.
