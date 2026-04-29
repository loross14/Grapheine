#!/usr/bin/env python3
"""graphene — graph-theoretic CLI for any folder of [[wikilinked]] markdown.

Your knowledge graph is a 2D lattice: notes as atoms, [[links]] as bonds.
This tool exposes the lattice — degree distribution, sublattices, cycles,
Dirac-point candidates (high-balance bridges), Fiedler value (algebraic
connectivity), and multi-source stack analysis.

Works on Obsidian, Logseq, Roam, Foam, Dendron, Quartz, Hugo content
trees, Notion exports, plain Zettelkasten, or any directory of `.md`
files using `[[wikilinks]]` and/or `[text](file.md)` references.

Read-side only. Pure stdlib. No app required.

Resolution:
  - Direct path: vault=/path/to/your/folder works for ANY directory of
    markdown files. This is the primary entry point.
  - Obsidian shortcut: registered vaults auto-detected from Obsidian's
    config (macOS: ~/Library/Application Support/obsidian/obsidian.json;
    Linux: ~/.config/obsidian/obsidian.json; Windows:
    %APPDATA%/obsidian/obsidian.json). Convenience for Obsidian users —
    pass vault=<basename> to select a registered vault by name.
  - Stack mode: vault=stack (or `*` if quoted) selects every leaf
    Obsidian vault for cross-source analysis.
  - vault=every includes parent/wrapper vaults too.
  - Set GRAPHENE_VAULT or OBSIDIAN_VAULT to change the default.

Commands:
  vaults [verbose]
  vault info=<name|path|files|size>
  read file=<name> | path=<rel>
  backlinks file=<name> [counts] [total] [format=text|json|tsv|csv]
  links file=<name> [total]
  unresolved [total] [verbose]
  orphans [total]
  aliases [file=<name>] [total] [verbose]
  tags [counts] [sort=count] [file=<name>] [total]
  tag name=<name> [verbose] [total]
  search query=<text> [path=<dir>] [limit=<n>] [case] [total] [format=text|json]
  search:context query=<text> [path=<dir>] [limit=<n>] [case]
  tasks [todo|done] [file=<name>|daily] [verbose]
  properties file=<name>
  property:get name=<key> file=<name>

Graph (math layer):
  graph degree [top=<n>]                  — degree distribution + top-N hubs
  graph hubs [top=<n>]                    — top-N nodes by degree
  graph triangles [total]                 — count 3-cycles (honeycomb=0)
  graph clustering                        — average local clustering coefficient
  graph girth                             — shortest cycle length
  graph bipartite                         — 2-color test; sublattice sizes
  graph components [verbose]              — connected components
  graph density                           — |E| / (|V|·(|V|-1)/2)
  graph dirac [top=<n>]                   — Dirac-point candidates
  graph spectrum [iters=<n>] [tol=<eps>]  — λ_max + Fiedler value
  graph layered [tperp=<f>|sweep=lo,hi,steps] [top=<n>] [verbose]
                                          — bilayer Hamiltonian + IPR localization

Multi-vault stack:
  health                                  — fingerprint (vault=* aggregates)
  moire [verbose]                         — pairwise vault overlap

Stack mode (vault=stack) is the stacked-bilayer Hamiltonian: each
source is a sheet, intra-source wikilinks are intra-layer hopping,
cross-source wikilinks are interlayer hopping. The operator form is
exact. Cross-sheet Dirac scoring (Shannon-entropy × degree over
sheet-membership) finds nodes that bridge layers. `graph layered`
makes the interlayer coupling t⊥ explicit and sweepable, computing
the weighted Laplacian's λ_max + Fiedler value and the inverse
participation ratio (IPR) of the algebraic-connectivity eigenvector
to identify coupling-driven localization regimes. Twist angle and
moiré supercells are not computed — those need lattice geometry the
source folders don't have. Operator algebra transfers; geometry doesn't.

License: MIT. © 2026 Logan Ross.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

# ── platform-aware registry ─────────────────────────────────────────────────

def _registry_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "obsidian" / "obsidian.json"
        return Path.home() / "AppData" / "Roaming" / "obsidian" / "obsidian.json"
    # linux + others
    cfg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(cfg) / "obsidian" / "obsidian.json"


REGISTRY = _registry_path()
SKIP_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".venv", "__pycache__"}

WIKILINK_RE = re.compile(r"\[\[([^\]\|#\^]+)(?:[#\^][^\]\|]*)?(?:\|[^\]]*)?\]\]")
MDLINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]*)?\)")
TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][\w/\-]*)")
TASK_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)$")
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


# ── arg parsing ──────────────────────────────────────────────────────────────

def parse_args(argv):
    if not argv:
        return None, {}, []
    cmd = argv[0]
    if cmd == "graph" and len(argv) > 1:
        cmd = f"graph:{argv[1]}"
        rest = argv[2:]
    else:
        rest = argv[1:]
    kv, flags = {}, []
    for a in rest:
        if "=" in a and not a.startswith("="):
            k, v = a.split("=", 1)
            kv[k] = v
        else:
            flags.append(a)
    return cmd, kv, flags


# ── vault resolution ─────────────────────────────────────────────────────────

def load_registry():
    if not REGISTRY.exists():
        return {}
    try:
        return json.loads(REGISTRY.read_text()).get("vaults", {})
    except Exception:
        return {}


def _default_vault_name():
    return os.environ.get("GRAPHENE_VAULT") or os.environ.get("OBSIDIAN_VAULT")


def resolve_vault(name):
    if not name:
        name = _default_vault_name()
    reg = load_registry()
    if not name:
        # first registered vault
        for v in reg.values():
            p = Path(v["path"])
            if p.is_dir():
                return p
        return None
    for v in reg.values():
        p = Path(v["path"])
        if p.name.lower() == name.lower():
            return p
    for vid, v in reg.items():
        if vid.startswith(name):
            return Path(v["path"])
    p = Path(name).expanduser()
    if p.is_dir():
        return p
    return None


def resolve_targets(name) -> list[Path]:
    """[vault] or list of vaults if name in {*, stack, all, every}.
    *|stack|all return only LEAF vaults (excluding any vault that contains
    another registered vault). every returns all registered vaults."""
    if not name:
        name = _default_vault_name()
    if name in ("*", "stack", "all", "every"):
        reg = load_registry()
        seen = set()
        candidates = []
        for v in reg.values():
            p = Path(v["path"])
            key = str(p)
            if p.is_dir() and key not in seen:
                candidates.append(p)
                seen.add(key)
        if name == "every":
            return candidates
        leaves = []
        for v in candidates:
            is_parent = any(other != v and v in other.parents for other in candidates)
            if not is_parent:
                leaves.append(v)
        return leaves
    p = resolve_vault(name)
    return [p] if p else []


def _as_list(v):
    if isinstance(v, Path):
        return [v]
    return list(v)


def walk_md(vaults):
    for vault in _as_list(vaults):
        for root, dirs, files in os.walk(vault):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith(".md"):
                    yield Path(root) / f


def vault_for(p, vaults):
    for v in _as_list(vaults):
        try:
            p.relative_to(v)
            return v
        except ValueError:
            continue
    return None


def rel(p, vaults):
    vs = _as_list(vaults)
    v = vault_for(p, vs)
    if v is None:
        return str(p)
    if len(vs) == 1:
        return str(p.relative_to(v))
    return f"{v.name}:{p.relative_to(v)}"


def resolve_file(vaults, file_arg, path_arg):
    vs = _as_list(vaults)
    if path_arg:
        for v in vs:
            p = v / path_arg
            if p.exists():
                return p
        return None
    if file_arg:
        target = file_arg.lower().rstrip("/")
        if target.endswith(".md"):
            target = target[:-3]
        idx = vault_index(vs)
        if target in idx:
            return idx[target][0]
    return None


# ── frontmatter (YAML-ish) ───────────────────────────────────────────────────

def parse_frontmatter(raw):
    out = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            items = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
                ln = lines[j].strip()
                if ln.startswith("- "):
                    items.append(ln[2:].strip().strip('"').strip("'"))
                elif ln.startswith("-"):
                    items.append(ln[1:].strip().strip('"').strip("'"))
                j += 1
            out[key] = items if items else ""
            i = j
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()] if inner else []
        else:
            out[key] = val.strip('"').strip("'")
        i += 1
    return out


def read_note(p):
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "", {}
    if "\r\n" in text:
        text = text.replace("\r\n", "\n")
    m = FM_RE.match(text)
    if m:
        return text[m.end():], parse_frontmatter(m.group(1))
    return text, {}


def fm_list(fm, key):
    v = fm.get(key)
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [s for s in v if s]
    if isinstance(v, str):
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            return [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
        return [s.strip().lstrip("#") for s in re.split(r"[,\s]+", v) if s.strip()]
    return []


# ── graph build (alias-aware, stack-aware) ──────────────────────────────────

_index_cache = {}


def vault_index(vaults):
    vs = _as_list(vaults)
    key = tuple(str(v) for v in vs)
    if key in _index_cache:
        return _index_cache[key]
    idx = defaultdict(list)
    for p in walk_md(vs):
        stem = p.stem.lower()
        if p not in idx[stem]:
            idx[stem].append(p)
        _, fm = read_note(p)
        for a in fm_list(fm, "aliases") + fm_list(fm, "alias"):
            ak = a.lower()
            if p not in idx[ak]:
                idx[ak].append(p)
    _index_cache[key] = idx
    return idx


_links_cache = {}


def collect_links(vaults):
    vs = _as_list(vaults)
    key = tuple(str(v) for v in vs)
    if key in _links_cache:
        return _links_cache[key]
    idx = vault_index(vs)
    forward = defaultdict(list)
    reverse = defaultdict(set)
    unresolved = defaultdict(set)
    files = []
    for p in walk_md(vs):
        files.append(p)
        body, _ = read_note(p)
        seen = set()
        for m in WIKILINK_RE.finditer(body):
            t = m.group(1).strip().lower()
            if t in seen or not t:
                continue
            seen.add(t)
            cands = idx.get(t)
            if cands:
                src_vault = vault_for(p, vs)
                tgt = next((c for c in cands if vault_for(c, vs) == src_vault), cands[0])
                if tgt != p:
                    forward[p].append(tgt)
                    reverse[tgt].add(p)
            else:
                unresolved[t].add(p)
        for m in MDLINK_RE.finditer(body):
            href = m.group(2).strip()
            try:
                if vault_for(p, vs) is None:
                    continue
                tgt = (p.parent / href).resolve()
                if tgt.exists() and any(tgt.is_relative_to(v) for v in vs) and tgt != p:
                    if tgt.stem.lower() not in seen:
                        seen.add(tgt.stem.lower())
                        forward[p].append(tgt)
                        reverse[tgt].add(p)
            except (ValueError, OSError):
                pass
    out = (forward, reverse, unresolved, files, idx)
    _links_cache[key] = out
    return out


def build_undirected_graph(vaults):
    forward, _, _, files, _ = collect_links(vaults)
    adj = defaultdict(set)
    for src, targets in forward.items():
        for tgt in targets:
            if tgt != src:
                adj[src].add(tgt)
                adj[tgt].add(src)
    for p in files:
        adj.setdefault(p, set())
    return adj


def _bfs_2_color(adj):
    color = {}
    odd = None
    for src in adj:
        if src in color:
            continue
        color[src] = 0
        q = deque([src])
        while q and odd is None:
            u = q.popleft()
            for v in adj[u]:
                if v not in color:
                    color[v] = 1 - color[u]
                    q.append(v)
                elif color[v] == color[u]:
                    odd = (u, v)
                    break
    return color, odd


# ── basic commands ──────────────────────────────────────────────────────────

def cmd_vaults(kv, flags):
    reg = load_registry()
    if not reg:
        print("(no vaults registered — is Obsidian installed?)", file=sys.stderr)
        return 1
    for vid, v in reg.items():
        name = Path(v["path"]).name
        if "verbose" in flags:
            print(f"{name}\t{v['path']}\t{vid}")
        else:
            print(name)
    return 0


def cmd_vault(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        print("vault not found", file=sys.stderr)
        return 2
    info = kv.get("info", "name")
    vault = vs[0]
    if info == "name":
        print(vault.name)
    elif info == "path":
        print(str(vault))
    elif info == "files":
        print(sum(1 for _ in walk_md(vs)))
    elif info == "size":
        print(sum(p.stat().st_size for p in walk_md(vs)))
    else:
        print(f"unknown info={info}", file=sys.stderr)
        return 2
    return 0


def cmd_read(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        print("vault not found", file=sys.stderr)
        return 2
    p = resolve_file(vs, kv.get("file"), kv.get("path"))
    if not p:
        print("file not found", file=sys.stderr)
        return 2
    sys.stdout.write(p.read_text(encoding="utf-8", errors="replace"))
    return 0


def cmd_backlinks(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    p = resolve_file(vs, kv.get("file"), kv.get("path"))
    if not p:
        print("file not found", file=sys.stderr)
        return 2
    forward, reverse, _, _, _ = collect_links(vs)
    incoming = reverse.get(p, set())
    if "total" in flags:
        print(len(incoming))
        return 0
    fmt = kv.get("format", "text")
    rows = sorted(incoming, key=lambda x: str(x))
    if "counts" in flags:
        counts = [(s, sum(1 for t in forward[s] if t == p)) for s in rows]
        if fmt == "json":
            print(json.dumps([{"file": rel(s, vs), "count": c} for s, c in counts]))
        else:
            sep = "," if fmt == "csv" else "\t"
            for s, c in counts:
                print(f"{rel(s, vs)}{sep}{c}")
    else:
        if fmt == "json":
            print(json.dumps([rel(s, vs) for s in rows]))
        else:
            for s in rows:
                print(rel(s, vs))
    return 0


def cmd_links(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    p = resolve_file(vs, kv.get("file"), kv.get("path"))
    if not p:
        print("file not found", file=sys.stderr)
        return 2
    body, _ = read_note(p)
    targets = []
    seen = set()
    for m in WIKILINK_RE.finditer(body):
        t = m.group(1).strip()
        if t.lower() not in seen:
            seen.add(t.lower())
            targets.append(t)
    for m in MDLINK_RE.finditer(body):
        stem = Path(m.group(2).strip()).stem
        if stem.lower() not in seen:
            seen.add(stem.lower())
            targets.append(stem)
    if "total" in flags:
        print(len(targets))
        return 0
    for t in targets:
        print(t)
    return 0


def cmd_unresolved(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    _, _, unresolved, _, _ = collect_links(vs)
    if "total" in flags:
        print(len(unresolved))
        return 0
    if "verbose" in flags:
        for tgt in sorted(unresolved):
            print(tgt)
            for s in sorted(unresolved[tgt], key=str):
                print(f"  {rel(s, vs)}")
    else:
        for tgt in sorted(unresolved):
            print(tgt)
    return 0


def cmd_orphans(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    _, reverse, _, files, _ = collect_links(vs)
    orphans = [p for p in files if p not in reverse]
    if "total" in flags:
        print(len(orphans))
        return 0
    for p in sorted(orphans, key=str):
        print(rel(p, vs))
    return 0


def cmd_aliases(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    if kv.get("file") or kv.get("path"):
        p = resolve_file(vs, kv.get("file"), kv.get("path"))
        if not p:
            print("file not found", file=sys.stderr)
            return 2
        _, fm = read_note(p)
        for a in fm_list(fm, "aliases") + fm_list(fm, "alias"):
            print(a)
        return 0
    rows = []
    for p in walk_md(vs):
        _, fm = read_note(p)
        for a in fm_list(fm, "aliases") + fm_list(fm, "alias"):
            rows.append((a, p))
    if "total" in flags:
        print(len(rows))
        return 0
    for a, p in rows:
        if "verbose" in flags:
            print(f"{a}\t{rel(p, vs)}")
        else:
            print(a)
    return 0


def _collect_tags(vaults):
    counter = Counter()
    by_file = defaultdict(set)
    for p in walk_md(vaults):
        body, fm = read_note(p)
        for t in TAG_RE.findall(body):
            counter[t] += 1
            by_file[p].add(t)
        for t in fm_list(fm, "tags"):
            t = t.lstrip("#")
            if t:
                counter[t] += 1
                by_file[p].add(t)
    return counter, by_file


def cmd_tags(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    if kv.get("file"):
        p = resolve_file(vs, kv.get("file"), kv.get("path"))
        if not p:
            print("file not found", file=sys.stderr)
            return 2
        _, by_file = _collect_tags(vs)
        for t in sorted(by_file.get(p, set())):
            print(t)
        return 0
    counter, _ = _collect_tags(vs)
    if "total" in flags:
        print(len(counter))
        return 0
    items = counter.most_common() if kv.get("sort") == "count" else sorted(counter.items())
    if "counts" in flags:
        for t, c in items:
            print(f"{t}\t{c}")
    else:
        for t, _ in items:
            print(t)
    return 0


def cmd_tag(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    name = kv.get("name", "").lstrip("#")
    if not name:
        print("name= required", file=sys.stderr)
        return 2
    _, by_file = _collect_tags(vs)
    matches = [p for p, ts in by_file.items() if name in ts]
    if "total" in flags:
        print(len(matches))
        return 0
    for p in sorted(matches, key=str):
        if "verbose" in flags:
            print(rel(p, vs))
        else:
            print(p.stem)
    return 0


def cmd_search(kv, flags, with_context=False):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    query = kv.get("query", "")
    if not query:
        print("query= required", file=sys.stderr)
        return 2
    case = "case" in flags
    needle = query if case else query.lower()
    limit = int(kv.get("limit", "0")) or None
    path_filter = kv.get("path")
    fmt = kv.get("format", "text")
    matches = []
    for p in walk_md(vs):
        if path_filter:
            v = vault_for(p, vs)
            if not v or not str(p.relative_to(v)).startswith(path_filter):
                continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        hay = text if case else text.lower()
        if needle in hay:
            if with_context:
                lines = []
                for i, ln in enumerate(text.splitlines(), 1):
                    h = ln if case else ln.lower()
                    if needle in h:
                        lines.append((i, ln))
                matches.append((p, lines))
            else:
                matches.append((p, None))
            if limit and len(matches) >= limit:
                break
    if "total" in flags:
        print(len(matches))
        return 0
    if fmt == "json":
        out = []
        for p, lines in matches:
            entry = {"file": rel(p, vs)}
            if lines is not None:
                entry["matches"] = [{"line": i, "text": t} for i, t in lines]
            out.append(entry)
        print(json.dumps(out))
        return 0
    for p, lines in matches:
        print(rel(p, vs))
        if with_context and lines:
            for i, ln in lines:
                print(f"  {i}: {ln}")
    return 0


def cmd_tasks(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    state = "todo" if "todo" in flags else ("done" if "done" in flags else None)
    file_arg = kv.get("file")
    if "daily" in flags:
        from datetime import date
        file_arg = date.today().isoformat()
    targets = [resolve_file(vs, file_arg, kv.get("path"))] if file_arg else list(walk_md(vs))
    targets = [t for t in targets if t]
    out = []
    for p in targets:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = TASK_RE.match(line)
            if not m:
                continue
            checked = m.group(1).lower() == "x"
            if state == "todo" and checked:
                continue
            if state == "done" and not checked:
                continue
            out.append((p, i, m.group(2), checked))
    if "verbose" in flags:
        last = None
        for p, i, t, c in out:
            if p != last:
                print(rel(p, vs))
                last = p
            print(f"  {i}: [{'x' if c else ' '}] {t}")
    else:
        for _, _, t, c in out:
            print(f"[{'x' if c else ' '}] {t}")
    return 0


def cmd_properties(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    p = resolve_file(vs, kv.get("file"), kv.get("path"))
    if not p:
        print("file not found", file=sys.stderr)
        return 2
    _, fm = read_note(p)
    for k, v in fm.items():
        if isinstance(v, list):
            print(f"{k}: [{', '.join(v)}]")
        else:
            print(f"{k}: {v}")
    return 0


def cmd_property_get(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    p = resolve_file(vs, kv.get("file"), kv.get("path"))
    if not p:
        print("file not found", file=sys.stderr)
        return 2
    name = kv.get("name", "")
    if not name:
        print("name= required", file=sys.stderr)
        return 2
    _, fm = read_note(p)
    v = fm.get(name)
    if v is None:
        return 0
    if isinstance(v, list):
        for item in v:
            print(item)
    else:
        print(v)
    return 0


# ── graph metrics ───────────────────────────────────────────────────────────

def cmd_graph_degree(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    degs = sorted((len(n) for n in adj.values()), reverse=True)
    if not degs:
        print("(empty graph)")
        return 0
    n = len(degs)
    mean = sum(degs) / n
    median = degs[n // 2] if n % 2 else (degs[n // 2 - 1] + degs[n // 2]) / 2
    hist = Counter(degs)
    print(f"nodes={n} edges={sum(degs)//2} mean_deg={mean:.3f} median_deg={median} max_deg={degs[0]}")
    print(f"isolated={hist.get(0,0)} deg=1:{hist.get(1,0)} deg=2:{hist.get(2,0)} deg=3:{hist.get(3,0)} deg≥10:{sum(c for d,c in hist.items() if d>=10)}")
    top = int(kv.get("top", "10"))
    if top:
        print(f"--- top-{top} hubs ---")
        ranked = sorted(adj.items(), key=lambda kv2: -len(kv2[1]))[:top]
        for p, nbrs in ranked:
            print(f"  {len(nbrs):4d}  {rel(p, vs)}")
    return 0


def cmd_graph_hubs(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    top = int(kv.get("top", "20"))
    ranked = sorted(adj.items(), key=lambda kv2: -len(kv2[1]))[:top]
    for p, nbrs in ranked:
        print(f"{len(nbrs):4d}\t{rel(p, vs)}")
    return 0


def cmd_graph_triangles(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    tri = 0
    for u, nbrs in adj.items():
        for v in nbrs:
            if str(v) <= str(u):
                continue
            tri += len(adj[u] & adj[v])
    tri //= 3
    if "total" in flags:
        print(tri)
        return 0
    print(f"triangles={tri}  (honeycomb expected: 0)")
    return 0


def cmd_graph_clustering(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    coeffs = []
    for u, nbrs in adj.items():
        k = len(nbrs)
        if k < 2:
            continue
        edges = 0
        nlist = list(nbrs)
        for i, a in enumerate(nlist):
            for b in nlist[i + 1:]:
                if b in adj[a]:
                    edges += 1
        coeffs.append((2 * edges) / (k * (k - 1)))
    if not coeffs:
        print("clustering=0.0")
        return 0
    avg = sum(coeffs) / len(coeffs)
    print(f"avg_local_clustering={avg:.4f}  n_evaluated={len(coeffs)}  (honeycomb expected: 0.0)")
    return 0


def cmd_graph_girth(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    best = float("inf")
    for src in adj:
        if best <= 3:
            break
        dist = {src: 0}
        parent = {src: None}
        q = deque([src])
        while q:
            u = q.popleft()
            if dist[u] >= best // 2 + 1:
                continue
            for v in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    parent[v] = u
                    q.append(v)
                elif parent[u] != v:
                    cycle = dist[u] + dist[v] + 1
                    if cycle < best:
                        best = cycle
    if best == float("inf"):
        print("girth=∞  (acyclic)")
    else:
        print(f"girth={best}  (honeycomb expected: 6)")
    return 0


def cmd_graph_bipartite(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    color, odd = _bfs_2_color(adj)
    a = sum(1 for c in color.values() if c == 0)
    b = sum(1 for c in color.values() if c == 1)
    if odd is None:
        print(f"bipartite=true  sublattice_A={a}  sublattice_B={b}  ratio={a/(b or 1):.3f}")
    else:
        u, v = odd
        print(f"bipartite=false  odd_edge={u.stem} ↔ {v.stem}")
        print(f"  partial_color: A={a} B={b}")
    return 0


def cmd_graph_components(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    seen = set()
    sizes = []
    for src in adj:
        if src in seen:
            continue
        comp = set()
        q = deque([src])
        while q:
            u = q.popleft()
            if u in comp:
                continue
            comp.add(u)
            seen.add(u)
            for v in adj[u]:
                if v not in comp:
                    q.append(v)
        sizes.append(len(comp))
    sizes.sort(reverse=True)
    print(f"components={len(sizes)}  largest={sizes[0] if sizes else 0}  isolates={sum(1 for s in sizes if s==1)}")
    if "verbose" in flags:
        for s in sizes[:20]:
            print(f"  {s}")
    return 0


def cmd_graph_density(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    n = len(adj)
    e = sum(len(v) for v in adj.values()) // 2
    if n < 2:
        print("density=NaN  (n<2)")
        return 0
    max_e = n * (n - 1) // 2
    print(f"density={e/max_e:.6f}  edges={e}  max_possible={max_e}  nodes={n}")
    return 0


def cmd_graph_dirac(kv, flags):
    """Dirac-point candidates: high-degree nodes whose neighborhoods balance
    the two sublattices of the bipartite tight-binding Hamiltonian. Same
    chiral-symmetry operator as graphene — different lattice, different
    spectrum, same algebraic structure. Single-vault uses the bipartite
    2-coloring as A/B; stack mode uses vault-of-origin as the sheet label.
    Score = balance × degree (single) or Shannon-entropy × degree (stack).
    Where the operator's two halves touch."""
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    multi = len(vs) > 1
    adj = build_undirected_graph(vs)
    if multi:
        color = {}
        for vi, v in enumerate(vs):
            for p in walk_md(v):
                color[p] = vi
        scored = []
        for u, nbrs in adj.items():
            if len(nbrs) < 4:
                continue
            bucket = Counter(color.get(v) for v in nbrs if color.get(v) is not None)
            if not bucket:
                continue
            total = sum(bucket.values())
            ent = -sum((c/total) * math.log(c/total) for c in bucket.values() if c > 0)
            score = ent * len(nbrs)
            label = "/".join(str(bucket.get(i, 0)) for i in range(len(vs)))
            home = vs[color[u]].name if color.get(u) is not None else "?"
            scored.append((score, len(nbrs), home, label, u))
        scored.sort(reverse=True)
        top = int(kv.get("top", "15"))
        print(f"  score   deg  home_sheet  spread ({'/'.join(v.name[:3] for v in vs)})  file")
        for s, d, h, l, p in scored[:top]:
            print(f"  {s:5.2f}  {d:4d}  {h:>10}  {l:>14}  {rel(p, vs)}")
    else:
        color, _ = _bfs_2_color(adj)
        scored = []
        for u, nbrs in adj.items():
            if len(nbrs) < 4:
                continue
            a = sum(1 for v in nbrs if color.get(v) == 0)
            b = sum(1 for v in nbrs if color.get(v) == 1)
            if a + b == 0:
                continue
            balance = min(a, b) / max(a, b)
            score = balance * len(nbrs)
            scored.append((score, len(nbrs), a, b, u))
        scored.sort(reverse=True)
        top = int(kv.get("top", "15"))
        print(f"{'score':>6}  {'deg':>4}  {'A/B':>9}  file")
        for s, d, a, b, p in scored[:top]:
            print(f"{s:6.2f}  {d:4d}  {a:>4}/{b:<4}  {rel(p, vs)}")
    return 0


def cmd_graph_spectrum(kv, flags):
    """λ_max + Fiedler value (algebraic connectivity).

    λ_max is the spectral radius of the Laplacian. Fiedler λ_2 is the
    smallest non-zero eigenvalue — large means well-connected, small
    means a narrow bottleneck (a near-cut)."""
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    adj = build_undirected_graph(vs)
    nodes = list(adj.keys())
    n = len(nodes)
    if n < 3:
        print("(graph too small)")
        return 0
    idx = {p: i for i, p in enumerate(nodes)}
    nbrs = [[idx[v] for v in adj[p]] for p in nodes]
    deg = [len(ns) for ns in nbrs]
    iters = int(kv.get("iters", "120"))
    tol = float(kv.get("tol", "1e-6"))

    def lap_apply(x):
        return [deg[i] * x[i] - sum(x[j] for j in nbrs[i]) for i in range(n)]

    def norm(x):
        return math.sqrt(sum(xi * xi for xi in x))

    def normalize(x):
        s = norm(x)
        return [xi / s for xi in x] if s > 0 else x

    def subtract_const(x):
        m = sum(x) / n
        return [xi - m for xi in x]

    rng = random.Random(0xC0FFEE)
    x = [rng.random() - 0.5 for _ in range(n)]
    x = normalize(x)
    # Phase 1: λ_max via power iteration on L. Skip convergence test on iter 0
    # to avoid a spurious match against the lam_max=0 sentinel when the random
    # init's first Rayleigh quotient happens to be near zero.
    lam_max = 0.0
    for it in range(iters):
        y = lap_apply(x)
        new = sum(xi * yi for xi, yi in zip(x, y))
        if it > 0 and abs(new - lam_max) < tol * (abs(lam_max) + 1):
            lam_max = new
            break
        lam_max = new
        x = normalize(y) if norm(y) > 0 else x

    x = [rng.random() - 0.5 for _ in range(n)]
    x = subtract_const(x)
    x = normalize(x)
    # Phase 2: λ_2 via shifted-deflated power iteration on M = lam_max·I − L,
    # restricted to the subspace orthogonal to the all-ones vector.
    mu = 0.0
    for it in range(iters):
        Lx = lap_apply(x)
        y = [lam_max * xi - lxi for xi, lxi in zip(x, Lx)]
        y = subtract_const(y)
        new = sum(xi * yi for xi, yi in zip(x, y))
        if it > 0 and abs(new - mu) < tol * (abs(mu) + 1):
            mu = new
            break
        mu = new
        x = normalize(y) if norm(y) > 0 else x

    fiedler = lam_max - mu
    print(f"lam_max≈{lam_max:.4f}   fiedler(λ_2)≈{fiedler:.6f}   nodes={n}")
    if fiedler < -tol:
        print(f"→ negative Fiedler ({fiedler:.6f}): Phase-1 likely undershot λ_max; "
              f"increase iters= or run on a smaller subgraph")
    elif fiedler < 1e-4:
        print("→ near-zero Fiedler: graph is effectively disconnected")
    elif fiedler < 0.05:
        print("→ small Fiedler: a narrow bottleneck exists between two regions")
    else:
        print("→ healthy connectivity")
    return 0


# ── layered (graphite) — bilayer Hamiltonian with explicit interlayer coupling ─

def build_layered_graph(vaults):
    """Multi-source stack as a layered tight-binding graph.

    Returns (nodes, idx, intra, inter, vault_of):
      nodes    — list[Path], canonical node order
      idx      — dict Path → int
      intra    — list[set[int]], intra-layer (same-vault) neighbors
      inter    — list[set[int]], inter-layer (cross-vault) neighbors
      vault_of — list[Path], vault of each node by index

    Cross-vault wikilinks become interlayer hops; same-vault wikilinks are
    intra-layer hops. Same operator decomposition as stacked graphene:
    H = (⊕_l H_l) + t⊥ · C, where each H_l is the in-layer adjacency and
    C is the interlayer adjacency. tperp scales C only.
    """
    forward, _, _, files, _ = collect_links(vaults)
    nodes = list(files)
    idx = {p: i for i, p in enumerate(nodes)}
    vs = _as_list(vaults)
    vault_of = [vault_for(p, vs) for p in nodes]
    n = len(nodes)
    intra = [set() for _ in range(n)]
    inter = [set() for _ in range(n)]
    for src, tgts in forward.items():
        if src not in idx:
            continue
        si = idx[src]
        for tgt in tgts:
            if tgt == src or tgt not in idx:
                continue
            ti = idx[tgt]
            same = vault_of[si] == vault_of[ti]
            if same:
                intra[si].add(ti)
                intra[ti].add(si)
            else:
                inter[si].add(ti)
                inter[ti].add(si)
    return nodes, idx, intra, inter, vault_of


def _weighted_lap_spectrum(intra, inter, tperp, iters, tol):
    """Weighted Laplacian L = D − W. Intra weight=1, inter weight=tperp.
    Returns (lam_max, fiedler_lambda, fiedler_vec)."""
    n = len(intra)
    deg = [len(intra[i]) + tperp * len(inter[i]) for i in range(n)]

    def lap_apply(x):
        out = [deg[i] * x[i] for i in range(n)]
        for i in range(n):
            s_intra = 0.0
            for j in intra[i]:
                s_intra += x[j]
            s_inter = 0.0
            for j in inter[i]:
                s_inter += x[j]
            out[i] -= s_intra + tperp * s_inter
        return out

    def norm(x):
        return math.sqrt(sum(xi * xi for xi in x))

    def normalize(x):
        s = norm(x)
        return [xi / s for xi in x] if s > 0 else x

    def subtract_const(x):
        m = sum(x) / n
        return [xi - m for xi in x]

    rng = random.Random(0xC0FFEE)
    x = normalize([rng.random() - 0.5 for _ in range(n)])
    lam_max = 0.0
    for it in range(iters):
        y = lap_apply(x)
        new = sum(xi * yi for xi, yi in zip(x, y))
        if it > 0 and abs(new - lam_max) < tol * (abs(lam_max) + 1):
            lam_max = new
            break
        lam_max = new
        x = normalize(y) if norm(y) > 0 else x

    x = normalize(subtract_const([rng.random() - 0.5 for _ in range(n)]))
    mu = 0.0
    fiedler_vec = x
    for it in range(iters):
        Lx = lap_apply(x)
        y = [lam_max * xi - lxi for xi, lxi in zip(x, Lx)]
        y = subtract_const(y)
        new = sum(xi * yi for xi, yi in zip(x, y))
        if it > 0 and abs(new - mu) < tol * (abs(mu) + 1):
            mu = new
            x = normalize(y) if norm(y) > 0 else x
            fiedler_vec = x
            break
        mu = new
        x = normalize(y) if norm(y) > 0 else x
        fiedler_vec = x

    fiedler = lam_max - mu
    return lam_max, fiedler, fiedler_vec


def _ipr(vec):
    """Inverse participation ratio of a normalized eigenvector.
    IPR = Σ ψ_i^4 with Σ ψ_i^2 = 1.
    1/n = fully delocalized (extended state).
    1   = fully localized on one node."""
    s2 = sum(v * v for v in vec)
    if s2 <= 0:
        return 0.0
    return sum((v * v / s2) ** 2 for v in vec)


def _parse_sweep(s):
    parts = s.split(",")
    if len(parts) != 3:
        raise ValueError("sweep= expects lo,hi,steps (e.g. 0,2,9)")
    lo, hi, steps = float(parts[0]), float(parts[1]), int(parts[2])
    if steps < 2:
        return [lo]
    return [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]


def cmd_graph_layered(kv, flags):
    """Layered tight-binding spectrum: bilayer/multilayer Hamiltonian with
    explicit interlayer coupling t⊥ on cross-vault wikilinks.

    Same operator algebra as stacked graphene: intra-layer hopping weight
    = 1.0, inter-layer hopping weight = t⊥. Sweeps t⊥ to find the regime
    where the Fiedler eigenvector localizes (high IPR) — coupling-driven
    pinch points where the stack's algebraic connectivity bottlenecks.

    Not magic-angle physics: we don't have lattice geometry, so there's
    no twist angle and no moiré supercell. The 'localized regime' here
    is identified by IPR of the algebraic-connectivity eigenvector, not
    by a Bistritzer-MacDonald calculation. Operator algebra transfers;
    geometric details don't."""
    if "vaults" in kv:
        # Comma-separated explicit list — works without an Obsidian registry.
        paths = [Path(s).expanduser() for s in kv["vaults"].split(",") if s.strip()]
        vs = [p for p in paths if p.is_dir()]
        if len(vs) != len(paths):
            missing = [str(p) for p in paths if not p.is_dir()]
            print(f"vaults= contained non-directories: {missing}", file=sys.stderr)
            return 2
    else:
        vs = resolve_targets(kv.get("vault") or "*")
    if len(vs) < 2:
        print("graph layered requires multi-vault stack (vault=stack, vault=*, or vaults=p1,p2,...)", file=sys.stderr)
        return 2
    nodes, idx_map, intra, inter, vault_of = build_layered_graph(vs)
    n = len(nodes)
    if n < 3:
        print("(stack too small)")
        return 0
    intra_e = sum(len(s) for s in intra) // 2
    inter_e = sum(len(s) for s in inter) // 2
    iters = int(kv.get("iters", "200"))
    tol = float(kv.get("tol", "1e-6"))
    top = int(kv.get("top", "10"))

    layers = {v: sum(1 for vo in vault_of if vo == v) for v in vs}
    layer_str = ", ".join(f"{v.name}:{layers[v]}" for v in vs)

    if "sweep" in kv:
        try:
            tperps = _parse_sweep(kv["sweep"])
        except ValueError as e:
            print(f"sweep parse error: {e}", file=sys.stderr)
            return 2
        print(f"[LAYERED] stack n={len(vs)} layers=({layer_str}) intra_e={intra_e} inter_e={inter_e}")
        print(f"  sweep={kv['sweep']} ({len(tperps)} steps)")
        print(f"  {'tperp':>7}  {'lam_max':>9}  {'fiedler':>10}  {'IPR':>8}  {'n·IPR':>7}")
        rows = []
        for tperp in tperps:
            lam_max, fiedler, vec = _weighted_lap_spectrum(intra, inter, tperp, iters, tol)
            ipr = _ipr(vec)
            rows.append((tperp, lam_max, fiedler, ipr, vec))
            print(f"  {tperp:>7.3f}  {lam_max:>9.4f}  {fiedler:>10.6f}  {ipr:>8.4f}  {n * ipr:>7.2f}")
        peak = max(rows, key=lambda r: r[3])
        print()
        print(f"  → peak IPR={peak[3]:.4f} at tperp={peak[0]:.3f} (n·IPR={n * peak[3]:.2f})")
        print(f"  → fully delocalized would be IPR=1/n={1 / n:.6f}")
        if inter_e == 0:
            print(f"  → inter_edges=0: layers are wikilink-disconnected; tperp has no effect on the spectrum")
        if "verbose" in flags:
            print(f"\n  --- top-{top} Fiedler-localized notes at peak (tperp={peak[0]:.3f}) ---")
            vec = peak[4]
            ranked = sorted(range(n), key=lambda i: -abs(vec[i]))[:top]
            for i in ranked:
                vname = vault_of[i].name if vault_of[i] else "?"
                print(f"  {abs(vec[i]):.4f}  {vname:>14}  {rel(nodes[i], vs)}")
        return 0

    tperp = float(kv.get("tperp", "1.0"))
    lam_max, fiedler, vec = _weighted_lap_spectrum(intra, inter, tperp, iters, tol)
    ipr = _ipr(vec)
    print(f"[LAYERED] stack n={len(vs)} layers=({layer_str})")
    print(f"  intra_edges={intra_e}  inter_edges={inter_e}  tperp={tperp}")
    print(f"  lam_max≈{lam_max:.4f}  fiedler(λ_2)≈{fiedler:.6f}  IPR={ipr:.4f}")
    loc_factor = ipr * n
    if loc_factor < 2:
        verdict = "extended state (delocalized)"
    elif loc_factor < 10:
        verdict = "moderate localization"
    else:
        verdict = "strongly localized"
    print(f"  → {verdict} (n·IPR={loc_factor:.2f}; 1·IPR=1 means single-node, n·IPR=1 means uniform)")
    if inter_e == 0:
        print(f"  → inter_edges=0: layers are wikilink-disconnected; tperp does not affect the spectrum")
    ranked = sorted(range(n), key=lambda i: -abs(vec[i]))[:top]
    print(f"  --- top-{top} Fiedler-localized notes ---")
    for i in ranked:
        vname = vault_of[i].name if vault_of[i] else "?"
        print(f"  {abs(vec[i]):.4f}  {vname:>14}  {rel(nodes[i], vs)}")
    return 0


# ── moire & health ──────────────────────────────────────────────────────────

def cmd_moire(kv, flags):
    vs = resolve_targets(kv.get("vault") or "*")
    if len(vs) < 2:
        print("moire requires multi-vault stack (vault=* or vault=stack)", file=sys.stderr)
        return 2
    stems = {}
    for v in vs:
        s = set()
        for p in walk_md(v):
            s.add(p.stem.lower())
        stems[v] = s
    print(f"{'A':>14}  {'B':>14}  {'|A|':>5}  {'|B|':>5}  {'∩':>5}  {'∪':>5}  {'jaccard':>7}")
    pairs = []
    for i, v1 in enumerate(vs):
        for v2 in vs[i + 1:]:
            inter = stems[v1] & stems[v2]
            union = stems[v1] | stems[v2]
            jacc = len(inter) / len(union) if union else 0
            pairs.append((jacc, v1, v2, inter, union))
    pairs.sort(reverse=True)
    for j, v1, v2, inter, union in pairs:
        print(f"{v1.name:>14}  {v2.name:>14}  {len(stems[v1]):>5}  {len(stems[v2]):>5}  {len(inter):>5}  {len(union):>5}  {j:>7.4f}")
    if "verbose" in flags:
        all_inter = set()
        for _, _, _, inter, _ in pairs:
            all_inter |= inter
        print(f"\n--- shared stems (n={len(all_inter)}) ---")
        for s in sorted(all_inter)[:60]:
            print(f"  {s}")
    return 0


def cmd_health(kv, flags):
    vs = resolve_targets(kv.get("vault"))
    if not vs:
        return 2
    multi = len(vs) > 1
    if multi:
        print(f"[GRAPHENE] stack n={len(vs)}")
        agg_e = 0
        for v in vs:
            adj = build_undirected_graph(v)
            _, reverse, unresolved, files, _ = collect_links(v)
            n = len(files)
            e = sum(len(x) for x in adj.values()) // 2
            agg_e += e
            isolates = sum(1 for x in adj.values() if not x)
            orphans_n = sum(1 for p in files if p not in reverse)
            mean_deg = (2 * e / n) if n else 0
            print(f"  {v.name:>14}: nodes={n:>5} edges={e:>5} ⟨k⟩={mean_deg:>5.2f} "
                  f"orphans={orphans_n:>4} isolates={isolates:>4} unresolved={len(unresolved):>4}")
        adj_s = build_undirected_graph(vs)
        _, _, unresolved_s, files_s, _ = collect_links(vs)
        e_s = sum(len(x) for x in adj_s.values()) // 2
        cross = e_s - agg_e
        print(f"  {'stack':>14}: nodes={len(files_s):>5} edges={e_s:>5} cross_sheet={cross:>4} "
              f"unresolved={len(unresolved_s):>4}")
        return 0
    vault = vs[0]
    adj = build_undirected_graph(vs)
    _, reverse, unresolved, files, _ = collect_links(vs)
    counter, _ = _collect_tags(vs)
    n = len(files)
    e = sum(len(x) for x in adj.values()) // 2
    isolates = sum(1 for x in adj.values() if not x)
    orphans_n = sum(1 for p in files if p not in reverse)
    color, odd = _bfs_2_color(adj)
    a = sum(1 for c in color.values() if c == 0)
    b = sum(1 for c in color.values() if c == 1)
    bip = "true" if odd is None else "false"
    mean_deg = (2 * e / n) if n else 0
    print(f"[GRAPHENE] {vault.name}: nodes={n} edges={e} ⟨k⟩={mean_deg:.2f} "
          f"orphans={orphans_n} isolates={isolates} unresolved={len(unresolved)} "
          f"tags={len(counter)} bipartite={bip} A/B={a}/{b}")
    return 0


# ── dispatch ────────────────────────────────────────────────────────────────

COMMANDS = {
    "vaults": cmd_vaults,
    "vault": cmd_vault,
    "read": cmd_read,
    "backlinks": cmd_backlinks,
    "links": cmd_links,
    "unresolved": cmd_unresolved,
    "orphans": cmd_orphans,
    "aliases": cmd_aliases,
    "tags": cmd_tags,
    "tag": cmd_tag,
    "search": lambda k, f: cmd_search(k, f, with_context=False),
    "search:context": lambda k, f: cmd_search(k, f, with_context=True),
    "tasks": cmd_tasks,
    "properties": cmd_properties,
    "property:get": cmd_property_get,
    "graph:degree": cmd_graph_degree,
    "graph:hubs": cmd_graph_hubs,
    "graph:triangles": cmd_graph_triangles,
    "graph:clustering": cmd_graph_clustering,
    "graph:girth": cmd_graph_girth,
    "graph:bipartite": cmd_graph_bipartite,
    "graph:components": cmd_graph_components,
    "graph:density": cmd_graph_density,
    "graph:dirac": cmd_graph_dirac,
    "graph:spectrum": cmd_graph_spectrum,
    "graph:layered": cmd_graph_layered,
    "moire": cmd_moire,
    "health": cmd_health,
}


__version__ = "0.3.0"


def main():
    # Restore default SIGPIPE behavior on POSIX so `dirac ... | head` exits clean.
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    cmd, kv, flags = parse_args(sys.argv[1:])
    if cmd is None or cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd == "--version":
        print(f"graphene {__version__}")
        return 0
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print(f"available: {', '.join(sorted(COMMANDS))}", file=sys.stderr)
        return 2
    try:
        return COMMANDS[cmd](kv, flags) or 0
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
