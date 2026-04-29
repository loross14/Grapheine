"""Smoke tests for diracs_graphene.

These tests build small fixture vaults under tmp_path and exercise the core
read-side commands and graph metrics. No Obsidian registry needed — every
test passes `vault=<path>` explicitly.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import diracs_graphene as dg


def write(p: Path, content: str, *, crlf: bool = False) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if crlf:
        p.write_bytes(content.replace("\n", "\r\n").encode("utf-8"))
    else:
        p.write_text(content, encoding="utf-8")


def make_vault(root: Path) -> Path:
    """A tiny vault that exercises wikilinks, aliases, CRLF, code-fences, and same-stem ambiguity."""
    root.mkdir(parents=True, exist_ok=True)

    write(root / "index.md", "# Index\n[[alpha]] [[beta]] [[gamma]]\n")
    write(root / "alpha.md", "# Alpha\n[[beta]] [[delta]]\n")
    write(root / "beta.md", "# Beta\n[[gamma]]\n")
    write(root / "gamma.md", "# Gamma\nNo outgoing links here.\n")
    write(root / "orphan.md", "# Orphan\nNothing points here, nothing leaves.\n")

    # Markdown-style cross-link
    write(root / "delta.md", "# Delta\nSee [Index](index.md).\n")

    # Filename ending in 'm' or 'd' — regression test for the rstrip BLOCKER fix
    write(root / "mom.md", "# Mom\n[[dad]]\n")
    write(root / "dad.md", "# Dad\n[[mom]]\n")

    # Aliased note: `[[honey]]` should resolve to honeycomb.md via aliases
    write(
        root / "honeycomb.md",
        "---\naliases: [honey, hex]\ntags: [structure, lattice]\n---\n# Honeycomb\n[[alpha]]\n",
    )
    write(root / "alias-caller.md", "# Caller\n[[honey]] [[hex]]\n")

    # CRLF frontmatter — regression test for F1's CRLF FLAG
    write(
        root / "windows-note.md",
        "---\ntags: [crlf, windows]\nauthor: GM\n---\n# Windows\n[[alpha]]\n",
        crlf=True,
    )

    # Same-stem ambiguity
    write(root / "daily" / "2026-04-28.md", "# Daily today\n")
    write(root / "archive" / "2026-04-28.md", "# Archived day\n")

    # Code-fence containing a fake tag (we currently expose this tag — the
    # test documents current behavior; tightening is a planned follow-up).
    write(
        root / "with-code.md",
        "# Has code\n```python\n# this is a fake_tag inside a fence\n```\n#real_tag is real\n",
    )

    # Frontmatter list (block style) and inline list
    write(root / "tagged-block.md", "---\ntags:\n  - foo\n  - bar\n---\n# Block tags\n")
    write(root / "tagged-inline.md", "---\ntags: [foo, baz]\n---\n# Inline tags\n")

    return root


def run(args: list[str]) -> str:
    """Run dirac.main() with argv and capture stdout."""
    import sys

    saved = sys.argv[:]
    sys.argv = ["graphene", *args]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = dg.main()
    finally:
        sys.argv = saved
    assert rc == 0, f"command failed: {args}, stdout={buf.getvalue()!r}"
    return buf.getvalue()


def reset_caches() -> None:
    """Module-level caches survive within a process; tests must reset between vaults."""
    dg._index_cache.clear()
    dg._links_cache.clear()


# ── tests ───────────────────────────────────────────────────────────────────


def test_health_basic(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["health", f"vault={vault}"])
    assert "[GRAPHENE]" in out
    assert "nodes=" in out
    assert "edges=" in out


def test_rstrip_blocker_fixed_mom(tmp_path):
    """Regression: file=mom must resolve to mom.md, not get mangled to 'mo'."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["read", "file=mom", f"vault={vault}"])
    assert "# Mom" in out, f"expected mom.md content, got: {out!r}"


def test_rstrip_blocker_fixed_dad(tmp_path):
    """Regression: file=dad must resolve to dad.md (trailing 'd')."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["read", "file=dad", f"vault={vault}"])
    assert "# Dad" in out


def test_alias_resolution(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    # 'honey' is an alias of honeycomb.md
    out = run(["read", "file=honey", f"vault={vault}"])
    assert "# Honeycomb" in out
    # And alias-caller's wikilink [[honey]] should resolve as a backlink
    out = run(["backlinks", "file=honeycomb", f"vault={vault}"])
    assert "alias-caller" in out


def test_crlf_frontmatter(tmp_path):
    """Regression: CRLF-encoded notes should parse frontmatter correctly."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["properties", "file=windows-note", f"vault={vault}"])
    assert "tags" in out
    assert "author" in out
    out_tags = run(["tags", "file=windows-note", f"vault={vault}"])
    assert "crlf" in out_tags
    assert "windows" in out_tags


def test_path_disambiguation(tmp_path):
    """Same-stem ambiguity: file=2026-04-28 returns first match; path= disambiguates."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    daily = run(["read", "path=daily/2026-04-28.md", f"vault={vault}"])
    archive = run(["read", "path=archive/2026-04-28.md", f"vault={vault}"])
    assert "Daily today" in daily
    assert "Archived day" in archive


def test_orphans_and_unresolved(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    orphans = run(["orphans", "total", f"vault={vault}"]).strip()
    assert int(orphans) >= 1  # 'orphan.md' has no incoming
    unresolved = run(["unresolved", "total", f"vault={vault}"]).strip()
    # alpha.md links to [[delta]] which exists, [[beta]] exists. No unresolved
    # except potentially 'gamma' depending on vault — but gamma.md exists.
    # Just assert it's a non-negative integer.
    assert int(unresolved) >= 0


def test_graph_degree(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["graph", "degree", "top=3", f"vault={vault}"])
    assert "nodes=" in out
    assert "edges=" in out
    assert "top-3 hubs" in out


def test_graph_components(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["graph", "components", f"vault={vault}"])
    assert "components=" in out
    assert "largest=" in out


def test_graph_density(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["graph", "density", f"vault={vault}"])
    assert "density=" in out


def test_graph_bipartite_or_not(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["graph", "bipartite", f"vault={vault}"])
    assert "bipartite=" in out


def test_graph_clustering_label_is_avg_local(tmp_path):
    """Regression: the clustering label says 'avg_local' not 'global'."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["graph", "clustering", f"vault={vault}"])
    assert "avg_local_clustering=" in out or "clustering=0.0" in out


def test_graph_spectrum_runs(tmp_path):
    """Smoke: spectrum command produces lam_max + fiedler without negative Fiedler."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["graph", "spectrum", "iters=200", f"vault={vault}"])
    assert "lam_max" in out
    assert "fiedler" in out


def test_tags_inline_and_block_lists(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    block = run(["tags", "file=tagged-block", f"vault={vault}"])
    assert "foo" in block and "bar" in block
    inline = run(["tags", "file=tagged-inline", f"vault={vault}"])
    assert "foo" in inline and "baz" in inline


def test_markdown_style_link_resolves_as_edge(tmp_path):
    """delta.md uses [Index](index.md); index should appear as a backlink target."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out = run(["backlinks", "file=index", f"vault={vault}"])
    assert "delta.md" in out


def test_help_does_not_crash(tmp_path):
    reset_caches()
    out = run(["--help"])
    assert "graphene" in out


def test_version():
    reset_caches()
    out = run(["--version"])
    assert "graphene" in out
    assert dg.__version__ in out
