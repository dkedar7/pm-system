"""pmkit command-line interface — the human-first surface over the backlog.

Usage::

    pmkit backlog list [--status S] [--sort score|created] [--limit N]
    pmkit backlog show <id>
    pmkit backlog add --target T --title ... --problem ... [--source URL ...]
    pmkit backlog promote <id>
    pmkit backlog approve <id> [--note ...]
    pmkit backlog status
    pmkit backlog export [--out PATH]
    pmkit discover <target> [...]          # added in U3

Every command accepts ``--json`` for machine-readable output so an agent can call the
same surface a human uses (parity).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .backlog import Backlog, BacklogError


def _open(args: argparse.Namespace) -> Backlog:
    return Backlog(getattr(args, "db", None))


def _emit(args: argparse.Namespace, human: str, payload) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(human)


def _truncate(text: str, width: int) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= width else text[: width - 3] + "..."


# --------------------------------------------------------------------- backlog
def cmd_backlog_list(args: argparse.Namespace) -> int:
    with _open(args) as bl:
        items = bl.list(status=args.status, sort=args.sort, limit=args.limit)
    if getattr(args, "json", False):
        print(json.dumps(items, indent=2, default=str))
        return 0
    if not items:
        print("(backlog empty)")
        return 0
    print(f"{'ID':>3}  {'STATUS':<9}  {'RICE':>7}  {'CATEGORY':<16}  TITLE")
    for it in items:
        score = "-" if it["rice"] is None else f"{it['rice']:.2f}"
        flag = " (!)" if it["low_confidence"] else ""
        print(
            f"{it['id']:>3}  {it['status']:<9}  {score:>7}  "
            f"{(it['category'] or '-'):<16}  {_truncate(it['title'], 50)}{flag}"
        )
    return 0


def cmd_backlog_show(args: argparse.Namespace) -> int:
    with _open(args) as bl:
        item = bl.get(args.id)
    if item is None:
        print(f"opportunity {args.id} not found", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(item, indent=2, default=str))
        return 0
    print(f"[{item['id']}] {item['title']}")
    print(f"  target      : {item['target']}")
    print(f"  status      : {item['status']}")
    print(f"  category    : {item['category'] or '-'}")
    score = "-" if item["rice"] is None else f"{item['rice']:.3f}"
    print(
        f"  RICE        : {score}  "
        f"(reach={item['reach']}, impact={item['impact']}, "
        f"confidence={item['confidence']}, effort={item['effort']})"
    )
    print(f"  low_conf.   : {item['low_confidence']}")
    if item["problem"]:
        print(f"  problem     : {item['problem']}")
    if item["sources"]:
        print("  sources     :")
        for s in item["sources"]:
            print(f"    - [{s.get('type','?')}] {s.get('url','?')}")
    if item["killtest"]:
        print("  kill-test   :")
        for v in item["killtest"]:
            print(f"    - {v.get('axis','?')}: {v.get('verdict','?')} — {v.get('reason','')}")
    if item["approval"]:
        print(f"  approval    : {item['approval']}")
    if item["delegation"]:
        print(f"  delegation  : {item['delegation']}")
    return 0


def cmd_backlog_add(args: argparse.Namespace) -> int:
    sources = [{"type": "manual", "url": u} for u in (args.source or [])]
    with _open(args) as bl:
        opp_id = bl.add_candidate(
            target=args.target,
            title=args.title,
            problem=args.problem or "",
            sources=sources,
            low_confidence=args.low_confidence,
        )
    _emit(args, f"added opportunity {opp_id}", {"id": opp_id})
    return 0


def cmd_backlog_promote(args: argparse.Namespace) -> int:
    try:
        with _open(args) as bl:
            bl.promote(args.id)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} promoted to 'specced'", {"id": args.id, "status": "specced"})
    return 0


def cmd_backlog_approve(args: argparse.Namespace) -> int:
    try:
        with _open(args) as bl:
            bl.approve(args.id, note=args.note)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} approved (gate cleared)", {"id": args.id, "status": "approved"})
    return 0


def cmd_backlog_categorize(args: argparse.Namespace) -> int:
    try:
        with _open(args) as bl:
            bl.set_category(args.id, args.category)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} categorized as {args.category}",
          {"id": args.id, "category": args.category})
    return 0


def cmd_backlog_spec(args: argparse.Namespace) -> int:
    try:
        with _open(args) as bl:
            bl.set_spec(args.id, args.path)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} spec recorded: {args.path}",
          {"id": args.id, "spec_path": args.path})
    return 0


def cmd_backlog_killtest(args: argparse.Namespace) -> int:
    """Persist kill-test verdicts and move new -> survived | pruned. Used by the
    pm-run orchestrator (and available to humans for parity)."""
    try:
        verdicts = json.loads(args.verdicts) if args.verdicts else []
    except json.JSONDecodeError as e:
        print(f"bad --verdicts JSON: {e}", file=sys.stderr)
        return 1
    reason = ""
    if getattr(args, "decide", False):
        from .killtest import decide_survival
        survived, reason = decide_survival(verdicts)
    else:
        survived = args.survived
    try:
        with _open(args) as bl:
            bl.record_killtest(args.id, verdicts, survived=survived)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    state = "survived" if survived else "pruned"
    human = f"opportunity {args.id} {state}" + (f" ({reason})" if reason else "")
    _emit(args, human, {"id": args.id, "status": state, "reason": reason})
    return 0


def cmd_backlog_score(args: argparse.Namespace) -> int:
    try:
        with _open(args) as bl:
            rice = bl.set_scores(args.id, args.reach, args.impact, args.confidence, args.effort)
    except (BacklogError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} scored: RICE={rice:.3f}",
          {"id": args.id, "rice": rice})
    return 0


def cmd_backlog_delegate(args: argparse.Namespace) -> int:
    """Record delegation of an approved item. Refuses without an approval record
    (the gate, enforced in backlog.record_delegation). The actual handoff to
    ce-plan/lfg is performed by the pm-run skill; this records the contract."""
    try:
        with _open(args) as bl:
            bl.record_delegation(args.id, spec_path=args.spec, target=args.target)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} delegated", {"id": args.id, "status": "delegated"})
    return 0


def cmd_backlog_ship(args: argparse.Namespace) -> int:
    try:
        with _open(args) as bl:
            bl.mark_shipped(args.id)
    except BacklogError as e:
        print(str(e), file=sys.stderr)
        return 1
    _emit(args, f"opportunity {args.id} marked shipped", {"id": args.id, "status": "shipped"})
    return 0


def cmd_backlog_status(args: argparse.Namespace) -> int:
    with _open(args) as bl:
        counts = bl.counts()
    if getattr(args, "json", False):
        print(json.dumps(counts, indent=2))
        return 0
    total = sum(counts.values())
    print(f"backlog: {total} opportunities")
    for status, n in counts.items():
        if n:
            print(f"  {status:<10} {n}")
    return 0


def cmd_backlog_export(args: argparse.Namespace) -> int:
    with _open(args) as bl:
        md = bl.export_markdown()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        _emit(args, f"exported backlog to {args.out}", {"out": args.out})
    else:
        print(md)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    from .connectors import get_connectors
    from .connectors.base import Config
    from .discover import run_discovery

    cfg = Config.from_env()
    try:
        connectors = get_connectors(args.source)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    with _open(args) as bl:
        summary = run_discovery(bl, args.target, connectors=connectors, cfg=cfg)
    if getattr(args, "json", False):
        print(json.dumps(summary, indent=2, default=str))
        return 0
    print(
        f"discovered for {summary['target']}: "
        f"{summary['new']} new, {summary['merged']} merged, "
        f"{summary['fetched']} signals fetched "
        f"({summary['low_confidence']} low-confidence)"
    )
    for src, n in summary["by_source"].items():
        print(f"  {src:<8} {n} signals")
    for skip in summary["skipped"]:
        print(f"  {skip['source']:<8} skipped - {skip['reason']}")
    return 0


# --------------------------------------------------------------------- parser
def cmd_dogfood_install(args: argparse.Namespace) -> int:
    from .dogfood.install import run_documented_install
    rep = run_documented_install(args.cmd or [])
    if getattr(args, "json", False):
        print(json.dumps(rep.to_dict(), indent=2))
    else:
        for s in rep.steps:
            tag = "ok " if s.ok else "GAP"
            print(f"  [{tag}] {s.command}" + ("" if s.ok else f"  -- {s.reason}"))
    return 0 if rep.all_ok else 1


def _emit_obs(args: argparse.Namespace, obs: list) -> int:
    if not obs:
        print("no observations recorded (empty step/call plan?)", file=sys.stderr)
        return 1  # exercising nothing is not a pass
    if getattr(args, "json", False):
        print(json.dumps(obs, indent=2, default=str))
    else:
        for o in obs:
            print(f"  [{'ok ' if o.get('ok') else 'FAIL'}] {o.get('step', '')}")
    return 0 if all(o.get("ok") for o in obs) else 1


def cmd_dogfood_ui(args: argparse.Namespace) -> int:
    from .dogfood.ui import drive_ui
    try:
        obs = drive_ui(args.url, json.loads(args.steps))
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    return _emit_obs(args, obs)


def cmd_dogfood_mcp(args: argparse.Namespace) -> int:
    import shlex

    from .dogfood.mcp import drive_mcp
    try:
        obs = drive_mcp(shlex.split(args.server), json.loads(args.calls))
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    return _emit_obs(args, obs)


def build_parser() -> argparse.ArgumentParser:
    # Shared global flags, attached to each leaf command so they work *after* the
    # subcommand (e.g. `pmkit backlog list --json`), which is what users/agents type.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--db", help="path to the backlog SQLite DB (default: ~/.pmkit/backlog.db)")
    common.add_argument(
        "--json", action="store_true", help="machine-readable JSON output")

    parser = argparse.ArgumentParser(prog="pmkit", description="pm-system opportunity funnel CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # discover (U3)
    p_disc = sub.add_parser("discover", parents=[common],
                            help="ingest signals for a target into candidates")
    p_disc.add_argument("target", help="owner/repo or ecosystem target")
    p_disc.add_argument("--source", action="append", help="limit to specific source(s)")
    p_disc.set_defaults(func=cmd_discover)

    # backlog
    p_bl = sub.add_parser("backlog", help="inspect and act on the opportunity backlog")
    bsub = p_bl.add_subparsers(dest="backlog_command", required=True)

    p_list = bsub.add_parser("list", parents=[common], help="list opportunities")
    p_list.add_argument("--status", choices=[
        "new", "survived", "pruned", "specced", "approved", "delegated", "shipped"])
    p_list.add_argument("--sort", choices=["score", "created"], default="score")
    p_list.add_argument("--limit", type=int)
    p_list.set_defaults(func=cmd_backlog_list)

    p_show = bsub.add_parser("show", parents=[common], help="show one opportunity")
    p_show.add_argument("id", type=int)
    p_show.set_defaults(func=cmd_backlog_show)

    p_add = bsub.add_parser("add", parents=[common], help="add an opportunity manually")
    p_add.add_argument("--target", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--problem", default="")
    p_add.add_argument("--source", action="append", help="source URL (repeatable)")
    p_add.add_argument("--low-confidence", dest="low_confidence", action="store_true")
    p_add.set_defaults(func=cmd_backlog_add)

    p_prom = bsub.add_parser("promote", parents=[common],
                             help="promote a survived item to 'specced'")
    p_prom.add_argument("id", type=int)
    p_prom.set_defaults(func=cmd_backlog_promote)

    p_appr = bsub.add_parser("approve", parents=[common],
                             help="approve a specced item (the human gate)")
    p_appr.add_argument("id", type=int)
    p_appr.add_argument("--note")
    p_appr.set_defaults(func=cmd_backlog_approve)

    p_cat = bsub.add_parser("categorize", parents=[common],
                            help="set a product category on an opportunity")
    p_cat.add_argument("id", type=int)
    p_cat.add_argument("--category", required=True,
                       choices=["agent-only", "human-and-agent"])
    p_cat.set_defaults(func=cmd_backlog_categorize)

    p_spec = bsub.add_parser("spec", parents=[common],
                             help="record the drafted requirements doc path")
    p_spec.add_argument("id", type=int)
    p_spec.add_argument("--path", required=True)
    p_spec.set_defaults(func=cmd_backlog_spec)

    p_kt = bsub.add_parser("killtest", parents=[common],
                           help="record kill-test result (new -> survived|pruned)")
    p_kt.add_argument("id", type=int)
    kt_grp = p_kt.add_mutually_exclusive_group(required=True)
    kt_grp.add_argument("--survived", dest="survived", action="store_true")
    kt_grp.add_argument("--pruned", dest="survived", action="store_false")
    kt_grp.add_argument("--decide", action="store_true",
                        help="apply the survival rule from --verdicts (already-solved is dispositive)")
    p_kt.add_argument("--verdicts", help="JSON array of per-axis verdicts")
    p_kt.set_defaults(func=cmd_backlog_killtest, survived=None)

    p_score = bsub.add_parser("score", parents=[common],
                              help="set RICE sub-scores (computes the composite)")
    p_score.add_argument("id", type=int)
    p_score.add_argument("--reach", type=float, required=True)
    p_score.add_argument("--impact", type=float, required=True)
    p_score.add_argument("--confidence", type=float, required=True)
    p_score.add_argument("--effort", type=float, required=True)
    p_score.set_defaults(func=cmd_backlog_score)

    p_del = bsub.add_parser("delegate", parents=[common],
                            help="record delegation of an approved item (gated)")
    p_del.add_argument("id", type=int)
    p_del.add_argument("--spec", help="spec path (defaults to the recorded spec_path)")
    p_del.add_argument("--target", help="implementation target (defaults to the opportunity target)")
    p_del.set_defaults(func=cmd_backlog_delegate)

    p_ship = bsub.add_parser("ship", parents=[common],
                             help="mark a delegated item as shipped")
    p_ship.add_argument("id", type=int)
    p_ship.set_defaults(func=cmd_backlog_ship)

    p_stat = bsub.add_parser("status", parents=[common],
                             help="show counts by lifecycle status")
    p_stat.set_defaults(func=cmd_backlog_status)

    p_exp = bsub.add_parser("export", parents=[common], help="export a markdown snapshot")
    p_exp.add_argument("--out", help="write to this path instead of stdout")
    p_exp.set_defaults(func=cmd_backlog_export)

    # dogfood — acceptance-test helpers (pm-dogfood skill composes these)
    p_df = sub.add_parser("dogfood", help="acceptance-test a shipped product")
    dsub = p_df.add_subparsers(dest="dogfood_command", required=True)

    p_dfi = dsub.add_parser("install", parents=[common],
                            help="run documented install commands in a clean room")
    p_dfi.add_argument("--cmd", action="append", required=True,
                       help="a documented command, verbatim (repeatable)")
    p_dfi.set_defaults(func=cmd_dogfood_install)

    p_dfu = dsub.add_parser("ui", parents=[common],
                            help="drive a running app's UI in a real browser")
    p_dfu.add_argument("--url", required=True)
    p_dfu.add_argument("--steps", required=True, help="JSON list of {action,target,value}")
    p_dfu.set_defaults(func=cmd_dogfood_ui)

    p_dfm = dsub.add_parser("mcp", parents=[common],
                            help="drive an MCP server as a real client")
    p_dfm.add_argument("--server", required=True, help="server launch command (quoted)")
    p_dfm.add_argument("--calls", required=True, help="JSON list of {tool,args}")
    p_dfm.set_defaults(func=cmd_dogfood_mcp)

    return parser


def _force_utf8_output() -> None:
    """Print arbitrary web content (emoji, CJK) without crashing on legacy consoles.

    Windows defaults stdout to cp1252, which raises UnicodeEncodeError on any
    non-Latin1 character in a fetched title. Reconfigure to UTF-8 with replacement.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: Optional[list[str]] = None) -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
