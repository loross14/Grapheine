"""Smoke tests for graphite — write-side dual of grapheine.

Each command is the Legendre dual of a grapheine read. These tests build
small fixture vaults under tmp_path and verify the proposal output, the
canon_gate behavior, and the --apply path on writable fixtures.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import grapheine as dg
import graphite as gp


def write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def make_vault(root: Path) -> Path:
    """A small vault with: an unresolved wikilink, an orphan, divergent frontmatter."""
    root.mkdir(parents=True, exist_ok=True)

    # Two notes that point at a nonexistent target.
    write(root / "alpha.md", "---\ntags: [astro, journal]\nstatus: open\n---\n# Alpha\n[[ghost]]\n")
    write(root / "beta.md", "---\ntags: [astro]\nstatus: open\n---\n# Beta\n[[ghost]] [[alpha]]\n")
    # Orphan with shared tag — should attract a bond suggestion.
    write(root / "gamma.md", "---\ntags: [astro]\n---\n# Gamma\nNothing points here.\n")
    # File missing the common 'status' key (present on alpha + beta).
    write(root / "delta.md", "---\ntags: [astro]\n---\n# Delta\n[[alpha]]\n")

    # A code-fragment "wikilink" that should be filtered out by stub.
    write(root / "noise.md", "# Noise\n[[(\"x\" == \"y\")]]\n")

    return root


def reset_caches() -> None:
    dg._index_cache.clear()
    dg._links_cache.clear()


def run(args: list[str]) -> tuple[str, str, int]:
    """Run graphite.main() with argv, capture stdout+stderr, return (out, err, rc)."""
    import sys

    saved = sys.argv[:]
    sys.argv = ["graphite", *args]
    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = gp.main()
    finally:
        sys.argv = saved
    return out.getvalue(), err.getvalue(), rc


# ── filter ──────────────────────────────────────────────────────────────────


def test_looks_like_a_link_accepts_real_names():
    assert gp._looks_like_a_link("alpha")
    assert gp._looks_like_a_link("a16z-talent-team-support")
    assert gp._looks_like_a_link("daily/2026-04-28")
    assert gp._looks_like_a_link("_soc-index")


def test_looks_like_a_link_rejects_code_fragments():
    assert not gp._looks_like_a_link('("$x" == "y")')
    assert not gp._looks_like_a_link('emoji_i, emoji_j, count')
    assert not gp._looks_like_a_link('a -> b')
    assert not gp._looks_like_a_link('foo|bar')


def test_looks_like_a_link_rejects_placeholders_and_paths():
    assert not gp._looks_like_a_link("<project>")
    assert not gp._looks_like_a_link("{template}")
    assert not gp._looks_like_a_link("../parent")
    assert not gp._looks_like_a_link("/abs/path")


def test_slug_preserves_subdirectories():
    """Targets like `daily/2026-02-26` should map to a subdir, not be flattened."""
    assert gp._slug("daily/2026-02-26") == "daily/2026-02-26"
    assert gp._slug("projects/wolverine") == "projects/wolverine"
    # Forbidden chars within a segment still get replaced
    assert gp._slug('a/b:c') == "a/b_c"
    assert gp._slug("plain") == "plain"


def test_stub_path_for_subdir_target(tmp_path):
    """A subdir-shaped wikilink target should produce a path nested in the vault."""
    reset_caches()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "src.md").write_text("[[daily/2026-04-28]]\n", encoding="utf-8")
    out, _, rc = run(["stub", f"vault={vault}", "json"])
    assert rc == 0
    proposals = json.loads(out)
    # Normalize to POSIX form so the assertion holds on Windows (which emits
    # backslashes in path strings).
    paths = [Path(p["path"]).as_posix() for p in proposals]
    assert any(p.endswith("daily/2026-04-28.md") for p in paths)


def test_looks_like_a_link_rejects_bare_ints_and_empty():
    assert not gp._looks_like_a_link("10")
    assert not gp._looks_like_a_link("")
    assert not gp._looks_like_a_link("   ")
    assert not gp._looks_like_a_link("a" * 200)


# ── canon_gate ──────────────────────────────────────────────────────────────


def test_canon_ok_accepts_forge_and_claude():
    assert gp._canon_ok(Path.home() / "Desktop" / "forge")
    assert gp._canon_ok(Path.home() / "Desktop" / "forge" / "diracs-graphene")
    assert gp._canon_ok(Path.home() / ".claude")


def test_canon_ok_rejects_outside():
    assert not gp._canon_ok(Path("/tmp"))
    assert not gp._canon_ok(Path.home() / "Documents")


# ── stub ────────────────────────────────────────────────────────────────────


def test_stub_proposes_only_real_links(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out, _, rc = run(["stub", f"vault={vault}", "json"])
    assert rc == 0
    proposals = json.loads(out)
    targets = [p["target"] for p in proposals]
    assert "ghost" in targets
    # noise.md's `[[("x" == "y")]]` must not produce a stub
    for t in targets:
        assert "==" not in t
        assert "(" not in t


def test_stub_apply_inside_forge_writes_file(tmp_path):
    """When the vault is under forge, --apply should create the stub file.
    tmp_path is under /var/folders by default, which is NOT inside forge — so we
    monkey-patch FORGE_ROOTS to include tmp_path for this test."""
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    saved = gp.FORGE_ROOTS
    gp.FORGE_ROOTS = (tmp_path,)
    try:
        out, _, rc = run(["stub", f"vault={vault}", "--apply"])
        assert rc == 0
        assert (vault / "ghost.md").exists()
        body = (vault / "ghost.md").read_text()
        assert "Stub created from" in body
        assert "alpha" in body or "beta" in body
    finally:
        gp.FORGE_ROOTS = saved


def test_stub_apply_outside_forge_refuses(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    # Default FORGE_ROOTS does NOT include tmp_path → refuse.
    _, err, rc = run(["stub", f"vault={vault}", "--apply"])
    assert rc == 2
    assert "canon_gate" in err


# ── bond ────────────────────────────────────────────────────────────────────


def test_bond_proposes_for_orphan_with_shared_tags(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    out, _, rc = run(["bond", f"vault={vault}", "k=2", "json"])
    assert rc == 0
    proposals = json.loads(out)
    # gamma.md is an orphan tagged 'astro'. bonds should link from peers to gamma.
    targets = [p["link_to"] for p in proposals]
    assert any("gamma" in t for t in targets)


# ── propagate ───────────────────────────────────────────────────────────────


def test_propagate_finds_missing_common_keys(tmp_path):
    reset_caches()
    vault = make_vault(tmp_path / "vault")
    # alpha+beta have 'status'; delta+gamma+noise don't. With min_share=0.4
    # (≥40% of 5 files), 'status' qualifies as common.
    out, _, rc = run(["propagate", f"vault={vault}", "min_share=0.4", "json"])
    assert rc == 0
    proposals = json.loads(out)
    paths_with_status = [p["path"] for p in proposals if "status" in p["keys"]]
    assert any("delta.md" in p for p in paths_with_status)


# ── legendre ────────────────────────────────────────────────────────────────


def test_legendre_table_prints():
    out, _, rc = run(["legendre"])
    assert rc == 0
    assert "Legendre table" in out
    assert "graphite stub" in out
    assert "graphite bond" in out
    assert "graphite propagate" in out


# ── help ────────────────────────────────────────────────────────────────────


def test_help_does_not_crash():
    out, _, rc = run(["--help"])
    assert rc == 0
    assert "graphite" in out
    assert "Legendre" in out


def test_unknown_command_returns_2():
    _, err, rc = run(["nope"])
    assert rc == 2
    assert "unknown command" in err
