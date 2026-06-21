"""pm-dogfood deterministic helpers.

The pm-dogfood *skill* owns inference and judgment (infer the usage scenario from a
product's docs, decide what counts as a gap, confirm reproducibility). This package holds
the mechanical, unit-testable pieces it calls: the clean-room install runner, the UI and
MCP drivers, the report/parity builder, and the confirmed+deduped backlog filer.
"""
