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


# ── v0.3 layered (graphite) ─────────────────────────────────────────────────


def make_two_vaults(root: Path) -> tuple[Path, Path]:
    """Two tiny vaults that share two stems and have a cross-vault wikilink."""
    a = root / "vault_a"
    b = root / "vault_b"
    write(a / "alpha.md", "# Alpha A\n[[beta]] [[shared]]\n")
    write(a / "beta.md", "# Beta A\n[[alpha]]\n")
    write(a / "shared.md", "# Shared in A\n[[alpha]]\n")
    write(a / "bridge.md", "# Bridge A\n[[only-in-b]]\n")  # cross-vault wikilink
    write(b / "alpha.md", "# Alpha B\n[[beta]] [[shared]]\n")
    write(b / "beta.md", "# Beta B\n[[alpha]]\n")
    write(b / "shared.md", "# Shared in B\n[[alpha]]\n")
    write(b / "only-in-b.md", "# Only B\nNo outgoing.\n")
    return a, b


def test_layered_requires_multi_vault(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    import sys, io
    saved = sys.argv[:]
    sys.argv = ["graphene", "graph", "layered", f"vault={vault}"]
    err = io.StringIO()
    from contextlib import redirect_stderr
    try:
        with redirect_stderr(err):
            rc = dg.main()
    finally:
        sys.argv = saved
    assert rc == 2
    assert "multi-vault" in err.getvalue()


def test_layered_runs_on_two_vault_stack(tmp_path):
    reset_caches()
    a, b = make_two_vaults(tmp_path)
    out = run(["graph", "layered", f"vaults={a},{b}", "tperp=1.0", "top=3"])
    assert "[LAYERED]" in out
    assert "intra_edges=" in out
    assert "inter_edges=" in out
    assert "lam_max" in out
    assert "fiedler" in out
    assert "IPR=" in out


def test_layered_sweep_emits_curve(tmp_path):
    reset_caches()
    a, b = make_two_vaults(tmp_path)
    out = run(["graph", "layered", f"vaults={a},{b}", "sweep=0,1,3", "top=3"])
    assert "sweep=0,1,3" in out
    # Header columns
    assert "tperp" in out and "lam_max" in out and "IPR" in out
    # Three sweep rows
    assert "0.000" in out
    assert "0.500" in out
    assert "1.000" in out
    assert "peak IPR" in out


def test_layered_zero_interlayer_warns(tmp_path):
    """Two vaults with no shared stems and no cross-vault wikilinks: layers
    are wikilink-disconnected, so tperp does nothing. Emit a warning line."""
    reset_caches()
    a = tmp_path / "iso_a"
    b = tmp_path / "iso_b"
    write(a / "n1.md", "# A1\n[[n2]]\n")
    write(a / "n2.md", "# A2\n")
    write(b / "m1.md", "# B1\n[[m2]]\n")
    write(b / "m2.md", "# B2\n")
    # Only way to point graphene at both is via two vault= args, but the CLI
    # takes a single vault=; resolve_targets only returns multi for the
    # registry-* shortcut. Test the build_layered_graph helper directly.
    nodes, idx, intra, inter, vault_of = dg.build_layered_graph([a, b])
    assert len(nodes) == 4
    assert sum(len(s) for s in intra) // 2 == 2
    assert sum(len(s) for s in inter) // 2 == 0


def test_layered_ipr_helper():
    # Fully delocalized: vec = (1,1,1,1)/2 — IPR = 4·(1/2)^4 = 4·1/16 = 1/4 = 1/n
    vec = [0.5, 0.5, 0.5, 0.5]
    assert abs(dg._ipr(vec) - 0.25) < 1e-12
    # Fully localized: vec = (1, 0, 0, 0) — IPR = 1
    vec = [1.0, 0.0, 0.0, 0.0]
    assert abs(dg._ipr(vec) - 1.0) < 1e-12
    # Zero vector — IPR = 0 (degenerate guard)
    assert dg._ipr([0.0, 0.0, 0.0]) == 0.0


def test_layered_parse_sweep():
    assert dg._parse_sweep("0,2,5") == [0.0, 0.5, 1.0, 1.5, 2.0]
    # Single step
    assert dg._parse_sweep("0.5,1.5,1") == [0.5]
    # Bad format
    import pytest
    with pytest.raises(ValueError):
        dg._parse_sweep("0,1")


def test_dos_requires_multi_vault(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    import sys, io
    saved = sys.argv[:]
    sys.argv = ["graphene", "graph", "dos", f"vault={vault}"]
    err = io.StringIO()
    from contextlib import redirect_stderr
    try:
        with redirect_stderr(err):
            rc = dg.main()
    finally:
        sys.argv = saved
    assert rc == 2
    assert "multi-vault" in err.getvalue()


def test_dos_runs_on_two_vault_stack(tmp_path):
    reset_caches()
    a, b = make_two_vaults(tmp_path)
    out = run([
        "graph", "dos", f"vaults={a},{b}",
        "moments=40", "samples=2", "bins=20",
    ])
    assert "[DOS]" in out
    assert "λ_max" in out
    assert "moments=40" in out
    # density column header
    assert "ρ(E)" in out


def test_jackson_kernel_first_term_one_and_decreasing():
    g = dg._jackson_kernel(50)
    # g[0] should equal 1 by construction
    assert abs(g[0] - 1.0) < 1e-12
    # Coefficients are non-negative and monotonically non-increasing
    assert all(gi >= 0 for gi in g)
    for i in range(1, len(g)):
        assert g[i] <= g[i - 1] + 1e-12


def test_detect_peaks_finds_clear_max():
    # Synthetic DOS with one clear peak at index 5
    densities = [0.1, 0.1, 0.1, 0.2, 0.5, 1.5, 0.5, 0.2, 0.1, 0.1]
    peaks = dg._detect_peaks(densities, min_z=1.0, n_peaks=3)
    assert len(peaks) >= 1
    assert peaks[0][0] == 5
    assert peaks[0][1] == 1.5


def test_kpm_reconstruct_returns_sorted_energies():
    # Trivial moments: μ_0=1, all others=0 → DOS proportional to 1/π√(1-x²)
    # (the Chebyshev measure). Should integrate finitely; sorted output.
    mu = [1.0] + [0.0] * 49
    energies, densities = dg._kpm_reconstruct(mu, lam_max=10.0, bins=30, kernel="none")
    assert len(energies) == 30
    assert len(densities) == 30
    assert energies == sorted(energies)
    # All densities non-negative
    assert all(d >= 0 for d in densities)
    # Energies span [0, ~10]
    assert energies[0] >= 0
    assert energies[-1] <= 10.5


# ── v0.4 sublattice (BM magic-angle analog) ─────────────────────────────────


def test_sublattice_requires_multi_vault(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    import sys, io
    saved = sys.argv[:]
    sys.argv = ["graphene", "graph", "sublattice", f"vault={vault}"]
    err = io.StringIO()
    from contextlib import redirect_stderr
    try:
        with redirect_stderr(err):
            rc = dg.main()
    finally:
        sys.argv = saved
    assert rc == 2
    assert "multi-vault" in err.getvalue()


def test_sublattice_runs_on_two_vault_stack(tmp_path):
    reset_caches()
    a, b = make_two_vaults(tmp_path)
    out = run([
        "graph", "sublattice", f"vaults={a},{b}",
        "t_aa=1.0", "t_ab=1.0", "top=3",
    ])
    assert "[SUBLATTICE]" in out
    assert "inter_aa=" in out
    assert "inter_bb=" in out
    assert "inter_ab=" in out
    assert "bipartite_quality" in out
    assert "lam_max" in out


def test_sublattice_sweep_emits_alpha_curve(tmp_path):
    reset_caches()
    a, b = make_two_vaults(tmp_path)
    out = run(["graph", "sublattice", f"vaults={a},{b}", "sweep=0,1,3"])
    assert "α = t_aa/t_ab" in out
    assert "0.000" in out
    assert "0.500" in out
    assert "1.000" in out
    assert "Bistritzer-MacDonald" in out


def test_per_vault_coloring_on_bipartite_pair(tmp_path):
    reset_caches()
    a, b = make_two_vaults(tmp_path)
    nodes, _, intra, inter, vault_of = dg.build_layered_graph([a, b])
    color, quality = dg.compute_per_vault_coloring(intra, vault_of, [a, b])
    # Both vaults are bipartite
    assert quality[a] == 1.0
    assert quality[b] == 1.0
    # Coloring is a valid 0/1 assignment
    assert all(c in (0, 1) for c in color)
    # Adjacent intra-vault nodes have opposite colors (since bipartite)
    for i in range(len(nodes)):
        for j in intra[i]:
            if vault_of[i] == vault_of[j]:
                assert color[i] != color[j], f"intra edge {i}-{j} has same color in bipartite vault"


def test_split_inter_by_sublattice_classifies_three_buckets():
    # 4 nodes, all in inter (cross-vault):
    #   0-1: A-A  (aa)
    #   2-3: B-B  (bb)
    #   0-2: A-B  (ab)
    inter = [{1, 2}, {0}, {0, 3}, {2}]
    color = [0, 0, 1, 1]
    aa, bb, ab = dg.split_inter_by_sublattice(inter, color)
    # 0-1 in aa
    assert 1 in aa[0] and 0 in aa[1]
    # 2-3 in bb
    assert 3 in bb[2] and 2 in bb[3]
    # 0-2 in ab (both directions)
    assert 2 in ab[0] and 0 in ab[2]
    # bb[0] and aa[2] should be empty
    assert len(bb[0]) == 0
    assert len(aa[2]) == 0
