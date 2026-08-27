# Simulation scope

The simulator accepts duration, sample rate, target altitude, initial battery, ambient temperature, noise, GPS availability, telemetry behavior, random seed, and a list of fault events. It generates a smooth, bounded altitude profile with approximate pressure/temperature trends, battery drain, GPS position, state transitions, and packet numbering. It supports GPS loss, radio interruption, packet drop/duplication/corruption/delay, sensor spike/freeze, battery anomaly, and software-restart event types.

It is designed for deterministic software verification. It is **not** a 6-DOF trajectory model, CFD solver, motor-performance predictor, weather model, flight-safety analysis, or replacement for OpenRocket/RASAero. Repeat runs use the saved scenario, seed, configuration version, and software version.
