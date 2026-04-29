# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] — 2026-04-28

Chemistry-claims correction. v0.2.0 over-softened in response to F3's
overclaim flag. Re-checking the math: F3 conflated "Hamiltonian is
identical" with "spectrum has Dirac cones" — the former is true on any
bipartite graph (operator form, chiral symmetry, ±E pairs); only the
latter requires lattice periodicity. v0.2.1 restores the strong claim.

### Changed
- **Title:** `Dirac's Graphene CLI tool for Knowledge Graphs` → `Dirac's
  Graphene — a tight-binding CLI for knowledge graphs`. "Tight-binding"
  is the literal physics term for the Hamiltonian we run on the
  wikilink graph.
- **README intuition section:** restored "This isn't metaphor — same
  Hamiltonian." Asserts that `H = -t Σ (a†b + h.c.)` is identical
  operator form for graphene and any bipartite tight-binding model.
  Lattice differs (3-regular periodicity vs arbitrary wikilink graph),
  so spectrum differs in detail — operator is the operator. Drops the
  defensive "Same chiral symmetry, not the same lattice" softening.
- **Stack mode framing:** restored "stacked-bilayer Hamiltonian" as
  exact (cross-source wikilinks ARE interlayer hopping in the operator
  form). What was metaphor was specifically the *twisted* qualifier —
  twist angle, moiré pattern, magic angle, flat bands. v0.2.1 keeps
  "stacked bilayer" (exact), drops "twisted bilayer with magic-angle
  physics" (metaphor).
- `cmd_graph_dirac` and top-level docstring rewritten to mirror the
  README's restored claim.

## [0.2.0] — 2026-04-28

Audit-pass response. The project keeps the same surface but lands the
five blockers from the entangled 5-facet audit, broadens the audience
beyond Obsidian, softens two README chemistry overclaims, renames the
console script from `dirac` to `graphene` (the read-side, sp²-bonded
sheet of the chemistry pair), and adds a test suite + CI matrix.

### Renamed
- **Console script: `dirac` → `graphene`.** The PyPI project stays
  `diracs-graphene` (Dirac's Graphene), but the binary is now
  `graphene` — the read-side, observing the lattice. A future companion
  `graphite` will be the write-side (stub unresolved wikilinks, suggest
  bonds). Naming rationale: `dirac` cohabits PyPI's `DIRAC` HEP-framework
  namespace (hundreds of `dirac-*` console scripts); `graphene` is
  a clean console name (graphene-python is library-only, libgraphene is
  homebrew-library-only). The chemistry framing — graphene reads,
  graphite writes — is the brand.
- Health output banner: `[DIRAC]` → `[GRAPHENE]`.
- Default vault env var: `DIRAC_VAULT` → `GRAPHENE_VAULT`.
  `OBSIDIAN_VAULT` still honored for backwards compatibility.

### Added
- `tests/` directory with 17 smoke tests covering core commands and
  regression cases for every BLOCKER fix.
- `.github/workflows/test.yml` — pytest matrix on Linux/macOS/Windows
  across Python 3.9–3.13.
- `[project.optional-dependencies].dev` — `pytest`, `ruff`, `build`,
  `twine`.
- README "Quick Start" with sample STDOUT.
- README "Troubleshooting" section.
- README "What this isn't" disambiguation against the `DIRAC` HEP
  framework, the `dirac-graph` spectral geometry library, and the
  `obsidian-graphene` Obsidian plugin.
- `DIRAC_VAULT` environment variable as the new default-vault knob
  (`OBSIDIAN_VAULT` is still honored for backwards compatibility).
- Negative-Fiedler diagnostic in `dirac graph spectrum` that warns
  when Phase-1 power iteration likely undershot λ_max.

### Changed
- **Audience broadening.** `dirac` now markets as a CLI for *any* folder
  of `[[wikilinked]]` markdown — Obsidian, Logseq, Roam, Foam, Dendron,
  Quartz, Hugo content trees, plain Zettelkasten, etc. The Obsidian
  registry is a discovery shortcut, not a requirement.
- **README rewrite.** Drops the "Obsidian CLI" framing in favor of
  knowledge-graph-CLI positioning. Leads with the moat (cross-source
  wikilink resolution + spectral/topological metrics) instead of "no
  Obsidian required" (which isn't unique vs other standalone Python
  CLIs).
- README chemistry softened: "Same chiral symmetry, not the same
  lattice" replaces "Hamiltonian is identical" (`README.md:38`); the
  twisted-bilayer framing is now explicitly marked as a structural
  proxy rather than a moiré / magic-angle calculation.
- Examples switched to `vault=stack` (glob-free) instead of `vault=*`
  (which expands under zsh/bash). The `*`/`stack`/`all` synonyms still
  work in the source.
- Install instructions now lead with `pip install --user
  git+https://github.com/loross14/diracs-graphene` (no clone step
  needed). The clone path is documented as the alternative.
- Help text label corrected: `graph clustering` is now described as
  "average local clustering coefficient" (it always was — only the label
  said "global"). STDOUT key is now `avg_local_clustering=…`.
- `Topic :: Scientific/Engineering :: Information Analysis` and
  `:: Mathematics` classifiers added.
- Expanded keywords (logseq, roam, foam, dendron, zettelkasten,
  knowledge-graph, spectral-graph, dirac, bipartite, honeycomb, fiedler).
- Per-Python-minor classifiers added (3.9–3.13).
- `[project.urls]` now declares `Repository`, `Issues`, `Changelog`.
- Version moved to a single source of truth (`__version__` in
  `diracs_graphene.py`); the docstring/`--version` no longer hard-codes
  `0.1.0`.

### Fixed
- **BLOCKER:** `resolve_file` used `rstrip(".md")`, which strips a
  *character set* not a suffix. Files ending in `m` or `d` were
  silently mangled (`mom.md` → query `mo`). Replaced with an explicit
  `endswith(".md")` slice.
- **BLOCKER:** `pyproject.toml` Homepage URL pointed at the non-existent
  GitHub user `loganross`; corrected to `loross14`.
- **BLOCKER:** `README.md` install snippet `pip install --user .` had
  no preceding `git clone && cd` step. New users now get a one-line
  `pip install --user git+...` recipe that works without a clone.
- **BLOCKER:** `vault=*` glob-expanded under zsh/bash and broke the
  showcase command. README now uses `vault=stack`; quoting `vault='*'`
  is documented for users who want the literal glob.
- CRLF-encoded notes (Windows-authored) now have their frontmatter
  parsed correctly. Previously `FM_RE` (newline-only) silently skipped
  the frontmatter, leaving aliases/tags/properties empty.
- `BrokenPipeError` is now caught in `main()`, and `SIGPIPE` is reset to
  the default action on POSIX. `dirac graph hubs | head` no longer
  prints a Python traceback.
- Phase-1 power iteration in `graph spectrum` no longer fires its
  convergence test on iteration 0 (which used to short-circuit
  spuriously when the random init's first Rayleigh quotient happened
  near zero, poisoning Phase 2's deflation).
- Dead linear-scan fallback in `resolve_file` removed (the index
  already keys by stem for every `.md`; the fallback never fired
  usefully).

### Soft caveats added
- `cmd_graph_dirac` docstring now states explicitly that the score is a
  structural proxy, not a momentum-space Dirac cone (which would
  require lattice periodicity wikilink graphs don't have).
- Top-level docstring marks stack mode as a "structural proxy, not a
  literal moiré / magic-angle calculation."

## [0.1.0] — 2026-04-28

Initial release. Pure-stdlib single-file Python CLI; reads vault
registry, walks `.md` files, exposes wikilink graph; adds a
graph-theoretic math layer (degree, triangles, clustering, girth,
bipartite, components, density, Dirac-points, Fiedler value) and a
multi-vault stack mode (cross-vault wikilink resolution, moire overlap,
twisted-bilayer Dirac analysis). MIT, no Obsidian app required.
