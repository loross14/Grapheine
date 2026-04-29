#!/usr/bin/env python3
"""graphite — write-side dual of grapheine. From γράφω/graphein, the same root.

Where grapheine reads the lattice (degree, links, unresolved, frontmatter),
graphite proposes writes that satisfy what the read side measured as missing.
The relationship is Legendre: L(q, q̇) on the read side, H(q, p) on the
write side, sharing q. The conjugate momentum p is the obligation each
unmet read implies — a stub for every unresolved link, a bond for every
isolated bridge, a propagation for every frontmatter divergence.

Three commands, each the dual of a grapheine read:

    stub        ← unresolved      (broken wikilinks → stub files)
    bond        ← orphans + tags  (isolated notes → suggested cross-links)
    propagate   ← properties      (frontmatter divergence → additions)
    legendre                      (print the dual mapping table)

Dry-run by default. --apply writes the proposals — but only when the
resolved vault is under ~/Desktop/forge/ or ~/.claude/. Outside-forge
vaults always run dry; the proposal output is the deliverable.

Usage:
    python3 graphite.py stub vault=<name|path> [limit=N] [--apply]
    python3 graphite.py bond vault=<name|path> [k=3] [--apply]
    python3 graphite.py propagate vault=<name|path> [min_share=0.5] [--apply]
    python3 graphite.py legendre vault=<name|path>
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import grapheine as G

FORGE_ROOTS = (Path.home() / "Desktop" / "forge", Path.home() / ".claude")


def _canon_ok(vault_root: Path) -> bool:
    """canon_gate: --apply is only honored when writes land inside forge or .claude."""
    try:
        rv = vault_root.resolve()
    except OSError:
        return False
    return any(str(rv).startswith(str(r.resolve())) for r in FORGE_ROOTS)


def _slug(name: str) -> str:
    """Filesystem-safe slug from a wikilink target."""
    s = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
    return s or "untitled"


_NOT_A_LINK = re.compile(r'[()=!,*$"<>{}]|\.\.\.|->|\|')


def _looks_like_a_link(target: str) -> bool:
    """Filter out wikilink-shaped fragments that aren't real link names:
    code fragments (`("$x" == "y")`), template placeholders (`<project>`),
    path-relative artifacts (`../_moc`), and bare integers (`10`, `11`).
    A real link is a name, not a snippet."""
    t = target.strip()
    if not t or len(t) > 120:
        return False
    if _NOT_A_LINK.search(t):
        return False
    if t.startswith(".") or t.startswith("/"):
        return False
    if t.isdigit():
        return False
    return True


def _read_existing(p: Path) -> tuple[str, dict]:
    body, fm = G.read_note(p)
    return body, fm


# ─────────────────────────────────────────────────────────────────────────────
# Legendre kernel
# ─────────────────────────────────────────────────────────────────────────────
#
# Each command is structured as: read with grapheine → compute the conjugate
# momentum p (the unmet obligation) → emit the write H(q, p). Same kernel,
# three commands.

def _legendre(read_fn, dual_fn):
    """Apply the read→dual transform. Returns the list of write proposals."""
    return dual_fn(read_fn())


# ─────────────────────────────────────────────────────────────────────────────
# stub: dual of `unresolved`
# ─────────────────────────────────────────────────────────────────────────────

STUB_TEMPLATE = """---
status: stub
created_by: graphite
---

# {title}

> Stub created from {n} unresolved reference{s}.

## Backlinks

{backlinks}
"""


def _propose_stubs(vaults, limit=None):
    _, _, unresolved, _, _ = G.collect_links(vaults)
    vault_root = vaults[0] if isinstance(vaults, list) else vaults
    proposals = []
    for tgt in sorted(unresolved):
        if not _looks_like_a_link(tgt):
            continue
        sources = sorted(unresolved[tgt], key=str)
        title = tgt.strip()
        path = Path(vault_root) / f"{_slug(title)}.md"
        backlinks = "\n".join(f"- [[{G.rel(s, [vault_root]).rsplit('.', 1)[0]}]]" for s in sources)
        body = STUB_TEMPLATE.format(
            title=title,
            n=len(sources),
            s="" if len(sources) == 1 else "s",
            backlinks=backlinks or "_(none)_",
        )
        proposals.append({"action": "create", "path": str(path), "body": body, "target": tgt})
        if limit and len(proposals) >= limit:
            break
    return proposals


# ─────────────────────────────────────────────────────────────────────────────
# bond: dual of `orphans` + tag overlap
# ─────────────────────────────────────────────────────────────────────────────
#
# An orphan is a note with no backlinks. Its conjugate obligation is a bond:
# at least one [[link]] from somewhere natural. We rank candidates by shared
# tag set — the heuristic is that two notes with overlapping tags belong in
# each other's neighborhoods. We emit the highest-overlap pair as a "See
# also" addition to the most-tagged sibling.

def _file_tags(p):
    _, fm = G.read_note(p)
    return set(G.fm_list(fm, "tags") + G.fm_list(fm, "tag"))


def _propose_bonds(vaults, k=3):
    forward, reverse, _, files, _ = G.collect_links(vaults)
    orphans = [p for p in files if p not in reverse]
    if not orphans:
        return []
    tag_index = {p: _file_tags(p) for p in files}
    proposals = []
    for op in sorted(orphans, key=str):
        op_tags = tag_index[op]
        if not op_tags:
            continue
        scored = []
        for q in files:
            if q == op:
                continue
            share = op_tags & tag_index[q]
            if share:
                scored.append((len(share), q, share))
        scored.sort(reverse=True)
        if not scored:
            continue
        top = scored[:k]
        op_link = G.rel(op, vaults).rsplit(".", 1)[0]
        for n_share, q, share in top:
            proposals.append({
                "action": "append_link",
                "path": str(q),
                "link_to": op_link,
                "shared_tags": sorted(share),
                "score": n_share,
            })
    return proposals


# ─────────────────────────────────────────────────────────────────────────────
# propagate: dual of `properties`
# ─────────────────────────────────────────────────────────────────────────────
#
# For frontmatter keys present in ≥ min_share of files in the vault, propose
# adding them (with a TODO value) to files where they're missing. The
# obligation is "convergence to the vault's own conventions."

def _propose_propagate(vaults, min_share=0.5):
    files = list(G.walk_md(vaults))
    if not files:
        return []
    key_counts = Counter()
    file_fms = {}
    for p in files:
        _, fm = G.read_note(p)
        file_fms[p] = fm
        for k in fm.keys():
            key_counts[k] += 1
    n = len(files)
    common = {k for k, c in key_counts.items() if c / n >= min_share}
    if not common:
        return []
    proposals = []
    for p in files:
        missing = sorted(common - set(file_fms[p].keys()))
        if not missing:
            continue
        proposals.append({
            "action": "add_frontmatter_keys",
            "path": str(p),
            "keys": missing,
            "share": {k: round(key_counts[k] / n, 3) for k in missing},
        })
    return proposals


# ─────────────────────────────────────────────────────────────────────────────
# Apply (gated by canon_check)
# ─────────────────────────────────────────────────────────────────────────────

def _apply(proposals, vault_root):
    if not _canon_ok(vault_root):
        print(f"canon_gate: refusing --apply outside forge/.claude (vault={vault_root})", file=sys.stderr)
        return 2
    written = 0
    for prop in proposals:
        path = Path(prop["path"])
        action = prop["action"]
        if action == "create":
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prop["body"], encoding="utf-8")
            written += 1
        elif action == "append_link":
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            link_line = f"\n\n## See also\n- [[{prop['link_to']}]]\n"
            if f"[[{prop['link_to']}]]" in text:
                continue
            path.write_text(text + link_line, encoding="utf-8")
            written += 1
        elif action == "add_frontmatter_keys":
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if text.startswith("---\n"):
                end = text.find("\n---\n", 4)
                if end == -1:
                    continue
                fm_block = text[4:end]
                rest = text[end + 5:]
                additions = "\n".join(f"{k}: TODO" for k in prop["keys"])
                new = f"---\n{fm_block}\n{additions}\n---\n{rest}"
            else:
                additions = "\n".join(f"{k}: TODO" for k in prop["keys"])
                new = f"---\n{additions}\n---\n\n{text}"
            path.write_text(new, encoding="utf-8")
            written += 1
    print(f"applied {written}/{len(proposals)} proposals", file=sys.stderr)
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

def _resolve(kv):
    vs = G.resolve_targets(kv.get("vault"))
    if not vs:
        print("vault not found", file=sys.stderr)
        return None
    return vs


def cmd_stub(kv, flags):
    vs = _resolve(kv)
    if not vs:
        return 2
    limit = int(kv["limit"]) if "limit" in kv else None
    proposals = _propose_stubs(vs, limit=limit)
    if "--apply" in flags or "apply" in flags:
        return _apply(proposals, vs[0])
    if "json" in flags:
        print(json.dumps(proposals, indent=2))
    else:
        for p in proposals:
            print(f"create  {p['path']}  ({p['target']})")
        print(f"\n{len(proposals)} stub proposal(s)", file=sys.stderr)
    return 0


def cmd_bond(kv, flags):
    vs = _resolve(kv)
    if not vs:
        return 2
    k = int(kv.get("k", 3))
    proposals = _propose_bonds(vs, k=k)
    if "--apply" in flags or "apply" in flags:
        return _apply(proposals, vs[0])
    if "json" in flags:
        print(json.dumps(proposals, indent=2))
    else:
        for p in proposals:
            print(f"link    {p['path']:60s} → [[{p['link_to']}]]  (tags: {','.join(p['shared_tags'])})")
        print(f"\n{len(proposals)} bond proposal(s)", file=sys.stderr)
    return 0


def cmd_propagate(kv, flags):
    vs = _resolve(kv)
    if not vs:
        return 2
    share = float(kv.get("min_share", 0.5))
    proposals = _propose_propagate(vs, min_share=share)
    if "--apply" in flags or "apply" in flags:
        return _apply(proposals, vs[0])
    if "json" in flags:
        print(json.dumps(proposals, indent=2))
    else:
        for p in proposals:
            print(f"add fm  {p['path']}  +{','.join(p['keys'])}")
        print(f"\n{len(proposals)} propagate proposal(s)", file=sys.stderr)
    return 0


def cmd_legendre(kv, flags):
    print("Legendre table — read (grapheine) ↔ write (graphite)\n")
    rows = [
        ("q (state)",       "vault files + wikilinks",       "vault files + wikilinks"),
        ("q̇ (rate)",        "edits / reads observed",        "obligations to satisfy"),
        ("read command",    "grapheine unresolved",          "graphite stub"),
        ("",                "grapheine orphans",             "graphite bond"),
        ("",                "grapheine properties",          "graphite propagate"),
        ("invariants",      "vault root, file count",        "vault root, file count"),
    ]
    width_a = max(len(r[0]) for r in rows)
    width_b = max(len(r[1]) for r in rows)
    print(f"{'aspect':<{width_a}}  {'read (L)':<{width_b}}  write (H)")
    print("-" * (width_a + width_b + 30))
    for a, b, c in rows:
        print(f"{a:<{width_a}}  {b:<{width_b}}  {c}")
    return 0


COMMANDS = {
    "stub": cmd_stub,
    "bond": cmd_bond,
    "propagate": cmd_propagate,
    "legendre": cmd_legendre,
}


def main():
    cmd, kv, flags = G.parse_args(sys.argv[1:])
    if cmd is None or cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print(f"available: {', '.join(sorted(COMMANDS))}", file=sys.stderr)
        return 2
    return COMMANDS[cmd](kv, flags) or 0


if __name__ == "__main__":
    sys.exit(main())
