# pmkit

The human-first CLI for [pm-system](../README.md). Deterministic work — fetching signals,
backlog CRUD, dedup, and RICE math — lives here so a person can run it directly and an agent
can call the exact same surface.

```bash
uv tool install .        # or: pip install .
pmkit --help
```

Core is stdlib-only (no third-party dependencies), so install is trivial and offline-friendly.

The backlog database defaults to `~/.pmkit/backlog.db`; override with `PMKIT_DB_PATH`.
Every command accepts `--json` for machine-readable output (agent parity).
