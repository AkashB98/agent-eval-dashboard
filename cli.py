"""CLI: ingest / list / summary / check / demo / serve.

check exits 0 = all-green, 1 = warning, 2 = critical (CI gate), 3 = error.
"""

from __future__ import annotations

import argparse
import json
import sys

from health import check_exit_code, fleet_health, project_health
from store import Store


def cmd_ingest(args) -> int:
    store = Store(args.store)
    with open(args.artifact, encoding="utf-8") as fh:
        envelope = json.load(fh)
    summary = store.ingest(envelope)
    print(f"ingested {summary['run_id']} [{summary['tool']}] "
          f"headline={summary['headline']:.3f} status={summary['status']}")
    return 0


def cmd_list(args) -> int:
    store = Store(args.store)
    rows = store.manifest()
    if args.project:
        rows = [r for r in rows if r["tool"] == args.project]
    for r in rows:
        print(f"{r['tool']:34s} {r['run_id']:40s} {r['ts']} "
              f"{r['headline']:.3f} {r['status']}")
    return 0


def cmd_summary(args) -> int:
    store = Store(args.store)
    fleet = fleet_health(store)
    print(f"fleet: {fleet['status']}  ({fleet['n_tools']} tools, {fleet['n_runs']} runs)")
    for p in fleet["projects"]:
        delta = "" if p["delta"] is None else f" delta={p['delta']:+.3f}"
        latest = p["latest"]
        print(f"  [{p['status']:8s}] {p['tool']:34s} "
              f"{latest['headline_label']}={latest['headline']:.3f} "
              f"trend={p['trend']}{delta} findings={len(latest['findings'])}")
    if fleet["alerts"]:
        print(f"alerts ({len(fleet['alerts'])}):")
        for a in fleet["alerts"]:
            print(f"  [{a['severity']}] {a['tool']}: {a['title']}")
    return 0


def cmd_check(args) -> int:
    store = Store(args.store)
    if args.project:
        runs = store.runs_for(args.project)
        if not runs:
            print(f"no runs for {args.project}")
            return 3
        fleet = {"status": {"green": "all-green", "warning": "warning",
                            "critical": "critical"}[project_health(runs)["status"]]}
    else:
        fleet = fleet_health(store)
    print(f"fleet: {fleet['status']}")
    return check_exit_code(fleet)


def cmd_demo(_args) -> int:
    import demo
    demo.main()
    return 0


def cmd_serve(args) -> int:
    from server import serve
    serve(args.store, port=args.port, simulated=args.simulated)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent-eval-dashboard")
    ap.add_argument("--store", default="store",
                    help="run store directory (default: ./store)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="ingest one artifact JSON file")
    p.add_argument("artifact")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("list", help="list ingested runs")
    p.add_argument("--project", default=None)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("summary", help="print fleet health summary")
    p.set_defaults(fn=cmd_summary)

    p = sub.add_parser("check", help="CI gate: exit 0/1/2 for all-green/warning/critical")
    p.add_argument("--project", default=None)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("demo", help="one-command end-to-end demo")
    p.set_defaults(fn=cmd_demo)

    p = sub.add_parser("serve", help="serve dashboard + JSON API on localhost")
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--simulated", action="store_true",
                   help="banner the dashboard as simulated data")
    p.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
