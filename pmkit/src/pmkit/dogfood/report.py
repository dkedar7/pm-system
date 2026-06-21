"""Dogfood findings model, parity check, and report rendering.

Pure functions over the drivers' result shapes. An observation is a dict:
``{"step": str, "ok": bool, "observed": Any, "claim": str (optional)}``. The report
normalizes install + UI + MCP observations into per-interface pass/fail findings, adds
parity findings (UI vs MCP must agree), and renders agent/human-readable markdown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Finding:
    interface: str          # install | ui | mcp | parity
    title: str
    status: str             # pass | fail
    gap: bool
    claim: str = ""
    observed: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DogfoodReport:
    target: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def gaps(self) -> list[Finding]:
        return [f for f in self.findings if f.gap]

    def passed(self) -> bool:
        return not self.gaps

    def per_interface(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for f in self.findings:
            d = out.setdefault(f.interface, {"pass": 0, "fail": 0})
            d["pass" if f.status == "pass" else "fail"] += 1
        return out

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "passed": self.passed(),
            "per_interface": self.per_interface(),
            "findings": [f.to_dict() for f in self.findings],
        }


def from_install(install_report) -> list[Finding]:
    out: list[Finding] = []
    for s in install_report.steps:
        out.append(Finding(
            interface="install",
            title=s.command,
            status="pass" if s.ok else "fail",
            gap=s.gap,
            claim="documented install step succeeds",
            observed=s.reason or ("ok" if s.ok else (s.output or "")[:200]),
        ))
    return out


def _observations(interface: str, obs: Optional[list[dict]]) -> list[Finding]:
    out: list[Finding] = []
    for ob in obs or []:
        ok = ob.get("ok", True)
        out.append(Finding(
            interface=interface,
            title=str(ob.get("step", "")),
            status="pass" if ok else "fail",
            gap=not ok,
            claim=str(ob.get("claim", "")),
            observed=str(ob.get("observed", "")),
        ))
    return out


def parity_check(ui_state: dict, mcp_state: dict) -> list[Finding]:
    """Compare the two surfaces' end states on shared keys; divergence is a gap."""
    shared = set(ui_state) & set(mcp_state)
    diverged = [
        Finding(
            interface="parity",
            title=f"surfaces disagree on {k!r}",
            status="fail",
            gap=True,
            claim="UI and MCP surfaces agree (parity)",
            observed=f"ui={ui_state[k]!r} mcp={mcp_state[k]!r}",
        )
        for k in sorted(shared, key=str)
        if str(ui_state[k]) != str(mcp_state[k])
    ]
    if shared and not diverged:
        return [Finding("parity", "UI/MCP parity holds", "pass", gap=False,
                        claim="UI and MCP surfaces agree", observed=f"{len(shared)} keys match")]
    return diverged


def build_report(
    target: str,
    *,
    install=None,
    ui: Optional[list[dict]] = None,
    mcp: Optional[list[dict]] = None,
    ui_state: Optional[dict] = None,
    mcp_state: Optional[dict] = None,
) -> DogfoodReport:
    findings: list[Finding] = []
    if install is not None:
        findings += from_install(install)
    findings += _observations("ui", ui)
    findings += _observations("mcp", mcp)
    if ui_state is not None and mcp_state is not None:
        findings += parity_check(ui_state, mcp_state)
    return DogfoodReport(target, findings)


def render_markdown(report: DogfoodReport) -> str:
    lines = [f"# Dogfood report: {report.target}", ""]
    lines.append(f"**Result:** {'PASS' if report.passed() else 'GAPS FOUND'}")
    lines.append("")
    lines.append("## Per-interface")
    for iface, c in report.per_interface().items():
        lines.append(f"- {iface}: {c['pass']} pass, {c['fail']} fail")
    gaps = report.gaps
    lines.append("")
    lines.append(f"## Gaps ({len(gaps)})")
    if not gaps:
        lines.append("- none")
    for g in gaps:
        lines.append(f"- [{g.interface}] {g.title}")
        if g.claim:
            lines.append(f"  - claim: {g.claim}")
        if g.observed:
            lines.append(f"  - observed: {g.observed}")
    return "\n".join(lines)
