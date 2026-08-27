# Simulation scope

The simulator generates a smooth, bounded altitude profile with a 1000 m apogee, approximate pressure/temperature trends, battery drain, GPS position, state transitions, and packet numbering. It supports GPS loss, radio interruption, malformed packets, delayed packets, and battery anomaly scenarios.

It is designed for deterministic software verification. It is **not** a 6-DOF trajectory model, CFD solver, motor-performance predictor, weather model, flight-safety analysis, or replacement for OpenRocket/RASAero. Repeat runs use the saved scenario, seed, configuration version, and software version.
