"""Discovery connectors (implemented in U3).

Each connector fetches signals from one OSS source and returns normalized candidate
dicts with provenance. Connectors degrade gracefully: a missing key or a source error
skips that source rather than aborting the run.
"""
