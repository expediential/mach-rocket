# Architecture

```mermaid
flowchart LR
    A[Engineering artifacts] --> B[Mission configuration]
    B --> C[Simulation engine]
    C --> D[Fault injection]
    D --> E[Telemetry validation]
    E --> F[Dashboard and MissionTest]
    G[Real test / flight CSV] --> E
    E --> H[Comparison and discrepancy aid]
    H --> I[Report and configuration history]
    F --> J[(SQLite audit / runs)]
    I --> J
```

The FastAPI application is deliberately split into small services: `simulator.py`, `telemetry.py`, `comparison.py`, `ork.py`, and `security.py`. `main.py` composes those services into documented endpoints. SQLite stores project-scoped records, packet rows, an explicit active workspace, and indexed run/flight/investigation lookup fields; imported source bytes are retained under opaque artifact IDs and are never overwritten. The archive endpoint exports project metadata, entities, packets, and retained artifacts as a portable ZIP. SQLite is appropriate for a one-machine prototype; a collaborative deployment would replace it with PostgreSQL plus authentication and authorization.

The simulator is deterministic when given the same scenario and seed. It generates synthetic, bounded values for testing software pipelines, not high-fidelity aerodynamic prediction.
