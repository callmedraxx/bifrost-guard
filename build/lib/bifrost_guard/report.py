"""The Court's report (Law Rules 18, 19, 21, 22, 23). Plain words first, technical detail after."""
from __future__ import annotations

import json
import time

from .plain import is_plain
from .store import Store

OPERATOR_LIST = {"Note", "Question", "Known", "Duplicate", "Not valid"}


def _plain_block(f) -> list[str]:
    p = json.loads(f["plain"]) if f["plain"] else {}
    lines = [f"  - What happens: {p.get('what_happens', '(not written yet)')}",
             f"  - What it means: {p.get('what_it_means', '(not written yet)')}",
             f"  - What you need to do: {p.get('what_to_do', '(not written yet)')}"]
    if p and not all(is_plain(str(v)) for v in p.values()):
        lines.append("  - (These words are harder than Rule 19 allows. Ask the Court to rewrite them.)")
    return lines


def round_report(store: Store, round_id: int) -> str:
    r = store.round(round_id)
    fs = store.findings(round_id=round_id)
    material = [f for f in fs if f["verdict"] == "Material"]
    arbiter = [f for f in fs if f["stage"] == "arbiter"]
    waiting = [f for f in fs if f["stage"] in ("machine", "judges")]
    others = [f for f in fs if f["verdict"] in OPERATOR_LIST]
    out = [f"Material findings: {len(material)}", ""]
    state = "closed" if r["closed"] else "open"
    out += [f"Round {round_id} ({r['scope']} review, {state}) on commit {r['commit_sha'][:12]}."]
    if waiting:
        out.append(f"{len(waiting)} finding(s) are still being checked, so this count may still change.")
    if arbiter:
        out.append(f"{len(arbiter)} finding(s) need your decision (see below).")
    out.append("")

    if material:
        out.append("## Real problems (must be fixed before use)")
        for f in material:
            d = json.loads(f["data"])
            out.append(f"- #{f['id']}: {d.get('title')}")
            out += _plain_block(f)
        out.append("")

    if arbiter:
        out.append("## You decide (the judges did not agree, or someone appealed)")
        for f in arbiter:
            d = json.loads(f["data"])
            js = json.loads(f["judges"]) if f["judges"] else []
            out.append(f"- #{f['id']}: {d.get('title')}")
            for j in js:
                out.append(f"  - Judge {j.get('judge')}: {j.get('verdict') or 'no verdict'}. "
                           f"{j.get('what_it_means', '')}")
        out.append("")

    if others:
        out.append("## Your list (nothing here can block. No agent may act on it. Only you decide.)")
        for f in others:
            d = json.loads(f["data"])
            dup = f" (same as #{f['duplicate_of']})" if f["duplicate_of"] else ""
            out.append(f"- #{f['id']} [{f['verdict']}{dup}]: {d.get('title')}")
            out += _plain_block(f)
        out.append("")

    over = [(f, dd) for f in fs for dd in store.decisions(f["id"]) if dd["kind"] in ("overrule", "decide")]
    if over:
        out.append("## Arbiter decisions")
        for f, dd in over:
            tag = "Overruled by the Arbiter" if dd["kind"] == "overrule" else "Decided by the Arbiter"
            out.append(f"- #{f['id']}: {tag}: {dd['verdict']}. Reason: {dd['reason']}")
        out.append("")

    out.append("## Technical detail")
    out.append(f"- Rules fingerprint: {r['fingerprint']}")
    out.append(f"- Commit: {r['commit_sha']}" + (f" (fixes since {r['since_commit'][:12]})" if r["since_commit"] else ""))
    out.append(f"- Opened {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(r['opened']))}, "
               f"closes {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(r['closes']))}")
    for f in fs:
        d = json.loads(f["data"])
        m = json.loads(f["machine"]) if f["machine"] else None
        out.append(f"- #{f['id']} by {f['reviewer']}: {d.get('file', '?')}:{d.get('line', '?')}; "
                   f"verdict {f['verdict'] or f['stage']}; rules {json.loads(f['rules'] or '[]')}"
                   + (f"; machine check: {m['reason']}" if m else "")
                   + ("; outside this round's scope (Rule 5)" if f["out_of_scope"] else ""))
        for j in json.loads(f["judges"]) if f["judges"] else []:
            out.append(f"  - {j.get('judge')}: {j.get('verdict')}. {str(j.get('reasons', j.get('error', '')))[:600]}")
    return "\n".join(out)


def release_status(store: Store, release: str) -> str:
    rounds = store.rounds(release)
    if not rounds:
        return "No round has been held yet."
    counts = []
    for r in rounds:
        n = sum(1 for f in store.findings(round_id=r["id"]) if f["verdict"] == "Material")
        pending = any(f["stage"] in ("machine", "judges", "arbiter") for f in store.findings(round_id=r["id"]))
        counts.append((r, n, pending))
    closed = [c for c in counts if c[0]["closed"]]
    lines = []
    if len(closed) >= 3 and all(n > 0 for _, n, _ in closed[-3:]):
        lines.append("Three rounds in a row found real problems. Fixing stops now. You decide: use it with "
                     "these problems listed, remove the feature, or redesign it (Rule 23).")
    last = counts[-1]
    full_held = any(r["scope"] == "full" and r["closed"] for r, _, _ in counts)
    if full_held and last[0]["closed"] and last[1] == 0 and not last[2]:
        lines.append("Ready: the full review was held and the latest round found no real problems. "
                     "Check that all tests pass, then the release is frozen (Rule 22).")
    elif not lines:
        lines.append("Not ready yet." + (" A round is still open." if not last[0]["closed"] else "")
                     + (" Some findings are still being checked or need your decision." if last[2] else "")
                     + (f" The latest round found {last[1]} real problem(s)." if last[1] else ""))
    return "\n".join(lines)
