# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-04-28

The Bistritzer–MacDonald analog. v0.3.x made `t⊥` sweepable and added
KPM density-of-states. v0.4 makes the **sublattice-resolved interlayer
coupling** explicit — `t_aa`, `t_bb`, `t_ab` as three independent knobs
on cross-vault edges classified by per-vault bipartite 2-coloring.
Sweeping `α = t_aa / t_ab` is the closest honest graph-theoretic cousin
of TBG's magic-angle condition `w_AA / w_AB ≈ 0.8`.

What transfers from TBG: the operator algebra (sublattice-resolved
coupling matrix, Fiedler/IPR diagnostics). What does NOT transfer:
lattice geometry, twist angle, moiré supercell, Brillouin zone,
Bistritzer–MacDonald continuum model. `graph sublattice` finds spectral
pinch points as a function of sublattice-resolved coupling — same
algebra as TBG, different lattice. The README's non-claim is preserved.

### Added

- **`graph sublattice`** command. Multi-vault only.
  - `t_aa=<f>`, `t_bb=<f>`, `t_ab=<f>` — three independent coupling
    weights. `t_bb` defaults to `t_aa` (homo-sublattice symmetry).
  - `sweep=lo,hi,steps` — sweeps `α = t_aa / t_ab` with `t_ab = 1` and
    `t_bb = t_aa`.
  - `top=<n>` — top-N Fiedler-localized notes printed under `verbose`,
    with sublattice label.
  - Reports per-vault `bipartite_quality` so users can tell whether the
    A/B classification of a given vault is trustworthy or confounded by
    intra-vault odd cycles.
- **`compute_per_vault_coloring(intra, vault_of, vs)` helper.** BFS
  2-colouring on intra-layer adjacency, per vault, with frustration
  counting. Multi-component vaults are seeded from the lowest-index
  node of each component (matches `_bfs_2_color`).
- **`split_inter_by_sublattice(inter, color)` helper.** Classifies each
  cross-vault edge into `inter_aa` / `inter_bb` / `inter_ab` adjacency
  lists.
- **`_make_lap_apply_sublattice(...)` factory.** Weighted Laplacian
  closure with three sublattice-resolved interlayer weights.
- **`_power_iter_lam_max` and `_fiedler` helpers.** Extracted from
  `_weighted_lap_spectrum` so the sublattice command can call them
  independently per α step. No behaviour change to the original.
- **5 new tests**: multi-vault required, runs on a 2-vault fixture,
  sweep emits the α curve and the BM citation, per-vault coloring
  validity on a bipartite pair, `split_inter_by_sublattice` puts edges
  in the right buckets.

### Changed

- Top-level docstring lists `graph sublattice`.
- README "Multi-source stack" section grew a `graph sublattice`
  subsection with the BM analogy and the explicit non-claim.

## [0.3.1] — 2026-04-28

The flat-band detector. v0.3.0 made interlayer coupling sweepable and
reported λ_max + Fiedler + IPR. v0.3.1 adds the **full spectral density
ρ(E)** via KPM (Kernel Polynomial Method) — the standard condensed-
matter tool for DOS in tight-binding models, used widely in real
disordered-graphene calculations. DOS peaks are the operator-level
signature of flat bands, computed honestly without invoking lattice
geometry we don't have.

### Added

- **`graph dos`** command. Multi-vault only.
  - `tperp=<f>` — interlayer coupling (default 1.0)
  - `moments=<n>` — Chebyshev expansion order (default 200)
  - `samples=<r>` — random probe vectors for trace estimator (default 8)
  - `bins=<k>` — output histogram resolution (default 100)
  - `peaks=<n>` — top-N peaks reported (default 5, threshold z ≥ 2)
  - `kernel=jackson|none` — default jackson (suppresses Gibbs oscillations)
  - `verbose` — print every bin (default samples evenly)
- **`_kpm_moments` helper.** Stochastic Chebyshev moments via Rademacher
  random vectors and the standard 3-term recurrence.
- **`_kpm_reconstruct` helper.** Reconstructs ρ(E) at arbitrary bins using
  Chebyshev nodes (denser sampling near band edges).
- **`_jackson_kernel` helper.** Closed-form Jackson kernel coefficients;
  `g[0] = 1`, monotonically non-increasing.
- **`_detect_peaks` helper.** Local-maxima detection with z-score
  thresholding.
- **`_resolve_multi_vaults(kv)` helper.** Centralized resolution of
  `vault=stack` / `vault=*` / `vaults=p1,p2,...`. Used by both
  `graph layered` and `graph dos`.
- **5 new tests**: multi-vault required, runs on a 2-vault fixture,
  Jackson kernel shape, peak detection on synthetic DOS, and KPM
  reconstruction sanity (sorted output, non-negative density).

### Changed

- **Refactor**: extracted `_make_lap_apply(intra, inter, tperp)` factory
  used by `_weighted_lap_spectrum` and the new KPM moment computation.
  No behavior change.
- Top-level docstring lists `graph dos`.

## [0.3.0] — 2026-04-28

The graphite extension. v0.2 made cross-source wikilinks resolve and
scored bridges via Shannon-entropy × degree (a structural stand-in for
"interlayer coupling"). v0.3 makes the interlayer coupling t⊥ an
**explicit, sweepable parameter** of the layered Hamiltonian and adds
**IPR localization** of the algebraic-connectivity eigenvector as the
diagnostic for coupling-driven spectral pinch points.

The algebra that transfers from stacked graphene:

```
H = (⊕_l H_l)  +  t⊥ · C
```

`H_l` = the existing within-layer adjacency operator; `C` = the
cross-vault wikilink adjacency between layers; `t⊥` = the interlayer
coupling weight. The Fiedler eigenvector's IPR (Σ ψᵢ⁴, normalized) tells
you which notes the algebraic-connectivity mode localizes on as t⊥
varies. What does *not* transfer: twist angle, moiré supercells, magic
angle. Those need lattice geometry the source folders don't have. The
operator is the operator; the lattice is your wikilink graph.

### Added

- **`graph layered`** command. Multi-vault only.
  - `tperp=<f>` for a single coupling.
  - `sweep=lo,hi,steps` to scan the coupling and emit a curve.
  - `top=<n>` to print the most localized notes by Fiedler magnitude.
  - `verbose` prints localized notes at the peak-IPR coupling during a sweep.
  - Reports `lam_max`, `fiedler(λ_2)`, `IPR`, and `n·IPR` for every step.
- **`vaults=p1,p2,p3` argument** (currently scoped to `graph layered`).
  Comma-separated explicit paths so users without an Obsidian registry
  can still build a stack from any directories.
- **`build_layered_graph(vaults)` helper.** Returns
  `(nodes, idx, intra, inter, vault_of)` — a clean separation of intra-
  vs inter-layer edges that downstream callers can reuse.
- **`_weighted_lap_spectrum(intra, inter, tperp, iters, tol)` helper.**
  Pure-stdlib weighted-Laplacian power iteration with the same shifted-
  deflated phase-2 used by `graph spectrum`. Returns `(λ_max, λ_2,
  Fiedler eigenvector)`.
- **`_ipr(vec)` helper.** Inverse participation ratio of a
  (re-)normalized eigenvector. Range `[1/n, 1]`.
- **6 new tests**: requires multi-vault, runs on a 2-vault fixture,
  emits a sweep curve, IPR identity check on uniform/single-node/zero
  vectors, sweep parser correctness, and `build_layered_graph` shape on
  a wikilink-disconnected pair.

### Changed

- Top-level docstring: `graph layered` added to the command list and
  the stack-mode prose now flags it as the explicit-coupling extension.
- README "Multi-source stack" section grew a `graph layered` subsection
  with a meaning-of-each-field table and an explicit non-claim about
  magic-angle / moiré (operator transfers; lattice doesn't).

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
