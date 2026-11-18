"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    for mid, val in (pr.get("metrics") or {}).items():
        if isinstance(val, float) and (not math.isfinite(val)):
            problems.append(f"{mid}: metric is NaN or inf")
    manifest = pr.get("manifest") or {}
    rows = pr.get("rows") or []
    item_count = manifest.get("items")
    seeds = manifest.get("seeds") or []
    if item_count is not None and isinstance(item_count, int):
        expected_rows = item_count * len(seeds)
        if len(rows) != expected_rows:
            problems.append(f"row count {len(rows)} != manifest {expected_rows}")
    pr_keys = {(r.get("item_id"), r.get("seed")) for r in rows}
    base_keys = {(r.get("item_id"), r.get("seed")) for r in (base.get("rows") or [])}
    if pr_keys != base_keys:
        problems.append("(item_id, seed) set differs from baseline")
    if pr.get("evaluator_failures"):
        problems.append("evaluator_failures is non-empty")
    graded_ids = {m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS}
    for i, row in enumerate(rows):
        for mid in graded_ids:
            if mid in row and row[mid] is None:
                problems.append(f"row {i}: {mid} is None")
    pr_slices = {r.get("item_id"): tuple(sorted(r.get("slices") or [])) for r in rows}
    base_slices = {r.get("item_id"): tuple(sorted(r.get("slices") or [])) for r in (base.get("rows") or [])}
    if pr_slices != base_slices:
        problems.append("item slice tags differ from baseline")

    if base_spec is not None:
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            base_metrics = {m["id"]: m for m in base_spec.get("metrics", [])}
            pr_metrics = {m["id"]: m for m in spec.get("metrics", [])}
            for mid, bm in base_metrics.items():
                pm = pr_metrics.get(mid)
                if pm is None:
                    problems.append(f"metric {mid} disappeared")
                    continue
                bt = bm.get("threshold") or {}
                pt = pm.get("threshold") or {}
                if "max" in bt and ("max" not in pt or pt["max"] > bt["max"]):
                    problems.append(f"metric {mid}: max threshold loosened")
                if "min" in bt and ("min" not in pt or pt["min"] < bt["min"]):
                    problems.append(f"metric {mid}: min threshold loosened")
                if "max_increase" in bt and ("max_increase" not in pt or pt["max_increase"] > bt["max_increase"]):
                    problems.append(f"metric {mid}: max_increase threshold loosened")
                if bm.get("blocking") and not pm.get("blocking"):
                    problems.append(f"metric {mid}: blocking became non-blocking")
            base_slices = {s["name"]: s for s in base_spec.get("slices", [])}
            pr_slices_spec = {s["name"]: s for s in spec.get("slices", [])}
            for name, bs in base_slices.items():
                ps = pr_slices_spec.get(name)
                if ps is None:
                    problems.append(f"slice {name} disappeared")
                    continue
                if "min" in bs and ("min" not in ps or ps["min"] < bs["min"]):
                    problems.append(f"slice {name}: min threshold loosened")
                if bs.get("blocking") and not ps.get("blocking"):
                    problems.append(f"slice {name}: blocking became non-blocking")
                if bs.get("no_significant_drop") and not ps.get("no_significant_drop"):
                    problems.append(f"slice {name}: no_significant_drop removed")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name = sl["name"]
        metric = sl["metric"]
        pr_item = per_item(pr, metric, slice_name=name)
        base_item = per_item(base, metric, slice_name=name)
        val = sum(pr_item.values()) / len(pr_item) if pr_item else 0.0
        verdict = "ok"
        note = ""
        if "min" in sl and val < sl["min"]:
            verdict = "fail"
        if sl.get("no_significant_drop"):
            keys = sorted(set(pr_item) & set(base_item))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_item[k] for k in keys], [base_item[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        sid = f"slice:{name}/{metric}"
        if verdict == "fail" and sl.get("blocking"):
            blocked.append(sid)
        label = "BLOCK" if verdict == "fail" and sl.get("blocking") else ("ok" if verdict == "ok" else "warn")
        lines.append(f"  {sid:<22} {val:<8.4f} {json.dumps(sl):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
