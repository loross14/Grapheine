# Grapheine — a tight-binding CLI for knowledge graphs

**Graph-theoretic CLI for any folder of `[[wikilinked]]` markdown.**

From Greek **γράφειν** (*graphein*, "to write") — the shared root of `graph`, `grapheme`, `grammar`, `paragraph`. The lattice this tool exposes is the *written* one.

Works on Obsidian vaults, Logseq graphs, Roam exports, Foam, Dendron, Quartz, Hugo content trees, Notion `.md` exports, plain Zettelkasten — anything with `[[name]]` or `[text](file.md)` references between markdown files.

Pure stdlib Python. No app, no plugin, no daemon, no REST.

> Your knowledge graph is a 2D lattice — notes as atoms, `[[links]]` as bonds. This tool exposes the lattice.

## Why this exists

Most knowledge-graph CLIs stop at backlinks and orphans. `grapheine` adds the layer that isn't elsewhere:

- **Cross-source wikilink resolution.** Point it at multiple folders (or all your registered Obsidian vaults at once) and links resolve across sources. Genuinely uncontested — Obsidian itself doesn't support cross-vault internal links.
- **Spectral & topological metrics.** Girth, bipartite test with sublattice sizes, Fiedler value (algebraic connectivity), Dirac-point candidates, density of states via KPM, sublattice-resolved interlayer coupling.
- **No app required.** Reads your folder directly. Doesn't launch Obsidian, doesn't need a plugin, doesn't need Node, doesn't need a REST endpoint.

## Quick start

```bash
# install (single command, no clone needed)
pip install --user git+https://github.com/loross14/Grapheine

# or from a clone
git clone https://github.com/loross14/Grapheine
cd Grapheine
pip install --user .
```

> If `grapheine` isn't found after install, ensure `~/.local/bin` is on your `PATH`.
> Windows: `pip install` is the recommended path; the POSIX-style copy/`chmod` recipe won't work on PowerShell/cmd.

Three commands, three outputs:

```bash
$ grapheine vaults
gitmoney
notes
research

$ grapheine health vault=notes
[GRAPHEINE] notes: nodes=512 edges=1834 ⟨k⟩=7.16 orphans=89 isolates=42 unresolved=27 tags=63 bipartite=false A/B=204/308

$ grapheine graph degree vault=notes top=5
nodes=512 edges=1834 mean_deg=7.165 median_deg=4 max_deg=78
isolated=42 deg=1:91 deg=2:67 deg=3:48 deg≥10:96
--- top-5 hubs ---
    78  index.md
    63  daily/2026-04-28.md
    51  reading-list.md
    44  projects/_moc.md
    37  people.md
```

## Pointing grapheine at any folder

`grapheine` works on any directory of markdown — Obsidian registry not required:

```bash
# any folder
grapheine health vault=/path/to/your/notes
grapheine graph degree vault=~/zettelkasten

# Obsidian users: shortcut by registered name
grapheine health vault=gitmoney

# multi-source stack (every leaf vault registered with Obsidian)
grapheine health vault=stack

# default: set GRAPHEINE_VAULT (legacy GRAPHENE_VAULT and OBSIDIAN_VAULT still honored)
export GRAPHEINE_VAULT=/path/to/your/notes
grapheine health
```

The Obsidian shortcut auto-detects the registry at:

- **macOS:** `~/Library/Application Support/obsidian/obsidian.json`
- **Linux native:** `~/.config/obsidian/obsidian.json`
- **Linux Flatpak:** `~/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json`
- **Linux Snap:** `~/snap/obsidian/current/.config/obsidian/obsidian.json`
- **Windows:** `%APPDATA%/obsidian/obsidian.json`

Currently auto-detected: macOS, Linux native, Windows. Flatpak/Snap users: pass `vault=/path/to/your/folder` directly. (PR welcome to extend auto-detection.)

## The intuition

Graphene — a single atomic layer of carbon, sp²-bonded into a hexagonal lattice — is a **bipartite honeycomb**: two interpenetrating sublattices A and B, where every A atom bonds to exactly three B atoms.

A wikilink graph has the same shape, structurally:

- **Atoms = notes.** Each `.md` file is a node.
- **Bonds = wikilinks.** Each `[[link]]` is an edge.
- **Sublattices = bipartite 2-coloring.** When the graph is bipartite, the two color classes act as A/B.
- **Dirac-point candidates = high-degree nodes whose neighborhoods are balanced across sublattices.** Where the two halves of your graph touch.
- **Stack mode = layered tight-binding.** Multiple folders/vaults stacked; cross-source wikilinks become interlayer bonds with explicit, sweepable coupling.

**This isn't metaphor — same Hamiltonian.** The graphene nearest-neighbor tight-binding Hamiltonian, `H = -t Σ_{<i,j>} (a_i† b_j + h.c.)`, is the bipartite adjacency operator. Run it on any bipartite graph and you get the same chiral symmetry, the same anticommutation with the sublattice operator σ_z, the same spectrum in ±E pairs. The lattice constant differs (graphene has 3-regular periodicity; your wikilink graph doesn't), so the *spectrum* differs in detail — but the *operator* is the operator. "Dirac-point candidates" means high-degree nodes whose neighborhoods balance the two sublattices: where the operator's two halves touch.

Stack mode is the **layered tight-binding Hamiltonian**: each source is a sheet, intra-source wikilinks are intra-layer hopping, cross-source wikilinks are interlayer hopping. The operator form is exact. `graph layered` makes the interlayer coupling `t⊥` an explicit, sweepable parameter. `graph dos` computes the spectral density via the Kernel Polynomial Method (the standard condensed-matter tool). `graph sublattice` resolves the interlayer coupling by sublattice pair (`t_aa`, `t_bb`, `t_ab`) — the closest honest graph-theoretic cousin of TBG's Bistritzer–MacDonald magic-angle ratio. What we *don't* compute is twist angle, moiré supercell, or magic-angle flat bands — those need lattice geometry the source folders don't have.

> If you don't care about the chemistry, skip to **Commands** — the math works regardless.

## Commands

### Basic

```bash
grapheine vaults                                       # list registered Obsidian vaults
grapheine vault info=name                              # current source info
grapheine read file=note-name                          # print a note's content
grapheine backlinks file=note-name [counts]            # what links to this note
grapheine links file=note-name                         # what this note links to
grapheine unresolved [verbose]                         # broken wikilinks
grapheine orphans                                      # files with no incoming links
grapheine aliases [file=note-name]                     # frontmatter aliases
grapheine tags [counts] [sort=count]                   # tag distribution
grapheine tag name=tagname [verbose]                   # files tagged with X
grapheine search query="text" [path=dir] [limit=N]
grapheine search:context query="text" [limit=N]        # with line context
grapheine tasks [todo|done] [file=note-name|daily]
grapheine properties file=note-name                    # frontmatter
grapheine property:get name=key file=note-name
```

### Graph math

```bash
grapheine graph degree [top=N]      # degree distribution + top hubs
grapheine graph hubs [top=N]        # top-N nodes by degree
grapheine graph triangles           # 3-cycles (honeycomb has 0)
grapheine graph clustering          # average local clustering coefficient
grapheine graph girth               # shortest cycle (honeycomb=6)
grapheine graph bipartite           # 2-color test; sublattice sizes
grapheine graph components          # connected components
grapheine graph density             # |E| / (|V|·(|V|-1)/2)
grapheine graph dirac [top=N]       # Dirac-point candidates (bridges)
grapheine graph spectrum            # λ_max + Fiedler value (algebraic connectivity)
grapheine graph layered ...         # bilayer Hamiltonian, t⊥-sweep, IPR (multi-vault only)
grapheine graph dos ...             # density of states via KPM (flat-band detector, multi-vault only)
grapheine graph sublattice ...      # sublattice-resolved coupling sweep (BM analog, multi-vault only)
```

### Multi-source stack

```bash
grapheine health vault=stack                       # fingerprint across leaf vaults
grapheine moire                                    # pairwise overlap (shared stems, Jaccard)
grapheine graph dirac vault=stack                  # cross-source Dirac points
grapheine graph layered vault=stack                # bilayer Hamiltonian, t⊥=1
grapheine graph layered vault=stack sweep=0,2,9    # sweep interlayer coupling
grapheine graph layered vaults=/path/a,/path/b     # without an Obsidian registry
grapheine graph dos vault=stack                    # density of states (flat-band detector)
grapheine graph sublattice vault=stack sweep=0,2,9 # BM-analog ratio sweep
```

`vault=stack` is the safe glob-free form of `vault=*`. Selects every leaf vault registered with Obsidian (vaults that don't contain another registered vault). Use `vault=every` to include parent/wrapper vaults too.

`vaults=p1,p2,p3` is the explicit alternative — comma-separated paths, no registry needed. Currently honored by `graph layered`, `graph dos`, and `graph sublattice`; other multi-vault commands still take `vault=stack`.

If your shell expands `*` (zsh/bash usually do), quote it: `vault='*'`.

#### `graph layered` — bilayer Hamiltonian with explicit interlayer coupling

`graph layered` builds the **layered tight-binding Hamiltonian** explicitly: each vault is a sheet, intra-vault wikilinks are intra-layer hopping with weight 1.0, cross-vault wikilinks are interlayer hopping with weight `t⊥`. Then it computes the weighted Laplacian's spectrum and the **inverse participation ratio (IPR)** of the Fiedler eigenvector.

```bash
# single coupling
grapheine graph layered vault=stack tperp=1.0 top=10

# sweep the coupling and watch the spectrum move
grapheine graph layered vault=stack sweep=0,2,9

# verbose: also print the localized notes at peak IPR
grapheine graph layered vault=stack sweep=0,2,9 verbose
```

| Output field | Meaning |
|---|---|
| `intra_edges` / `inter_edges` | within-vault vs cross-vault wikilinks |
| `lam_max` | spectral radius of the weighted Laplacian |
| `fiedler` | algebraic connectivity (λ₂) — bottleneck = small, well-connected = large |
| `IPR` | Σ ψᵢ⁴ of the normalized Fiedler eigenvector. `1/n` = fully delocalized; `1` = pinned to one note |
| `n·IPR` | normalized: `1.0` ≈ uniform, `n` = one node carries everything |

**Reading a sweep.** As `t⊥` rises from 0 (decoupled layers) to ∞ (fused into one graph), the Fiedler eigenvector deforms. Watch for an IPR peak — that's the regime where the algebraic-connectivity mode pinches onto a small set of notes. Those notes (printed with `verbose`) are the **interlayer-coupling-driven bottlenecks** of the stack.

**What this isn't.** This is *not* magic-angle physics. We don't have lattice geometry, so there's no twist angle, no moiré supercell, no Bistritzer–MacDonald flat-band calculation. The operator algebra (`H = (⊕_l H_l) + t⊥ · C`) transfers verbatim from stacked graphene; the geometric structure that makes 1.1° special does not. `graph layered` finds spectral pinch points as a function of explicit interlayer coupling — same algebra, different lattice.

#### `graph dos` — density of states via Kernel Polynomial Method

`graph dos` computes the **spectral density ρ(E) of the layered Laplacian** without diagonalizing it, using the standard condensed-matter Kernel Polynomial Method (Chebyshev expansion + Jackson kernel + stochastic trace estimation). DOS peaks are the measurable signature of flat bands — energies where many eigenvectors cluster — without invoking magic-angle geometry.

```bash
# default: 200 moments, 8 random probe vectors, 100 output bins
grapheine graph dos vault=stack tperp=1.0

# faster preview
grapheine graph dos vault=stack moments=120 samples=4 bins=80

# print every bin instead of every Nth + peaks
grapheine graph dos vault=stack moments=200 verbose
```

| Output field | Meaning |
|---|---|
| `λ_max` | spectral radius (sets the rescaling so spectrum lies in [−1, 1]) |
| `moments` | Chebyshev expansion order (resolution ≈ λ_max / N) |
| `samples` | random probe vectors averaged for the trace estimator |
| `bins` | output histogram resolution |
| `ρ(E)` | density of states at energy E (probability density over rescaled spectrum) |
| `peak` | local maxima with z-score ≥ 2 — flat-band candidates |

**The honest claim.** KPM is the standard tool for DOS in tight-binding models — used widely in real condensed-matter calculations of disordered graphene, TBG, and beyond. Running it on the layered wikilink Laplacian gives a *real* spectral density, computed from the *real* operator. **What we name 'flat-band candidate' is a DOS peak**: an energy where the eigenvalue distribution piles up. We do *not* claim this corresponds to any specific physical magic-angle phenomenon — that needs lattice geometry. We *do* claim DOS peaks are the operator-level signature you'd look for if you suspected localized modes, and KPM is how condensed-matter physicists actually compute them.

#### `graph sublattice` — sublattice-resolved interlayer coupling (BM analog)

The closest **honest** graph-theoretic cousin of the Bistritzer–MacDonald magic-angle condition. In real twisted bilayer graphene, the BM flat-band ratio is roughly `w_AA / w_AB ≈ 0.8` — homo-sublattice tunneling slightly weaker than hetero-sublattice. We have the same algebraic structure on a layered wikilink Laplacian:

1. Each vault gets a **per-vault bipartite 2-coloring** on its intra-layer adjacency. Sublattice A = colour 0, sublattice B = colour 1. (Reported per-vault as `bipartite_quality ∈ [0, 1]` — `1.0` is fully bipartite; `<1.0` means some intra-vault odd cycles frustrate the coloring.)
2. Each cross-vault edge is **classified** by sublattice pair: `aa` (both on A), `bb` (both on B), `ab` (mixed).
3. Three independent coupling weights — `t_aa`, `t_bb`, `t_ab` — replace the single `t⊥` of `graph layered`.
4. Sweep `α = t_aa / t_ab` (with `t_bb` defaulting to `t_aa` and `t_ab = 1`). Watch `λ_max`, Fiedler `λ_2`, and `n·IPR` move.

```bash
# fixed sublattice weights
grapheine graph sublattice vault=stack t_aa=0.8 t_ab=1.0

# BM-style ratio sweep — find spectral pinch points in α
grapheine graph sublattice vault=stack sweep=0,2,9

# verbose: print top-N localized notes (with their sublattice label) at peak α
grapheine graph sublattice vault=stack sweep=0,2,9 verbose top=10
```

**The honest non-claim.** This is not a Bistritzer–MacDonald calculation. We don't have lattice geometry; there's no Brillouin zone, no twist angle, no moiré supercell. What transfers is the **operator algebra**: same Hamiltonian decomposition, same sublattice-resolved coupling matrix, same Fiedler/IPR diagnostics. `graph sublattice` reports peaks in `n·IPR` as α varies — those are the operator-level cousins of the BM magic ratio. If you find a non-trivial α\* that pinches the algebraic-connectivity mode onto a small, sublattice-coherent set of notes, you've found the **operator's structural analog** of magic-angle behaviour. Whether anything physical or epistemic happens at that α\* on your graph is an empirical question the tool can't answer for you.

## Reading the output

| Metric | Honeycomb expected | What it tells you |
|---|---|---|
| `triangles` | 0 | Triadic shortcuts violate honeycomb structure |
| `avg_local_clustering` | 0.0 | Higher = your notes form cliques |
| `girth` | 6 | Shortest cycle. <6 means triangles or squares exist |
| `bipartite` | true | If false, no clean 2-coloring; sublattices not separable |
| `Fiedler λ_2` | "healthy" > 0.05 | Near zero = bottleneck; large = well-connected |
| `Dirac score` | high = strong bridge | `balance × degree` (single) or `entropy × degree` (stack) |
| `IPR` | n·IPR ≈ 1 = uniform | Higher = Fiedler mode pinches onto fewer notes |
| `DOS peak` | sharper = flatter band | Energies where many eigenvectors cluster |

A real knowledge graph rarely matches the clean honeycomb. The metrics tell you how far you are from it — and which notes anchor the structure.

## Frontmatter

Parses YAML-ish frontmatter:

```yaml
---
tags: [foo, bar]              # inline list
tags:
  - foo                        # block list
  - bar
aliases: [alt-name]
author: GM
---
```

Both `tags`/`tag` and `aliases`/`alias` keys are recognized. CRLF line endings (Windows) are normalized.

## Resolution rules

- `[[link]]` resolves by stem (filename without `.md`), case-insensitive, with alias matching.
- `[[link|alias]]`, `[[link#section]]`, `[[link^block]]` all resolve to `link`.
- `[text](path/to/note.md)` markdown-style links count as wikilinks.
- **Same-stem ambiguity:** when two files share a stem in different subdirectories (e.g. `daily/2026-01-15.md` and `archive/2026-01-15.md`), `file=` returns the first match in walk order. Use `path=relative/path/to/file.md` to disambiguate.
- In stack mode, same-source matches win; cross-source matches are the fallback.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `vault not found` | Pass an explicit path: `grapheine health vault=/abs/path/to/folder`. Or check `grapheine vaults` to list registered Obsidian vaults. |
| `(no vaults registered — is Obsidian installed?)` | You don't have an Obsidian config. Use `vault=/path/to/folder` instead of relying on the registry. |
| `command not found: grapheine` | Ensure your install location (e.g. `~/.local/bin`) is on `PATH`. Try `python3 -m grapheine <command>` to bypass. |
| Linux Flatpak / Snap users see no vaults | Auto-detection covers native paths only. Pass `vault=/path/to/folder` directly. |
| `grapheine graph spectrum` reports negative Fiedler | Phase-1 power iteration undershot λ_max. Increase `iters=200` or run on a smaller subgraph (`vault=specific-folder`). |

## What this isn't

- **Not affiliated with the GraphQL `graphene-python` library** on PyPI. We're `grapheine` (with the trailing *-eine*); they're `graphene` (with the trailing *-ene*). Different name, different ecosystem.
- **Not affiliated with `DIRAC`** — the HEP distributed-computing framework on PyPI (`pip install dirac`). They ship hundreds of `dirac-*` console scripts; we ship a single `grapheine`.
- **Not affiliated with `dirac-graph`** — the computational spectral geometry library by `pulquero`. Adjacent territory, different scope.
- **Not affiliated with the `obsidian-graphene` Obsidian plugin** by `suniyao` (vector-embedding graph view inside Obsidian). They invent edges from LLM embeddings; we run tight-binding operators on the literal `[[wikilink]]` graph.

The trailing *-eine* (γράφειν) is the disambiguating suffix. It's both a Greek root that ties to writing and a clean namespace island in the PyPI / Obsidian / GitHub neighborhood.

## Graphite — write-side companion

`grapheine` reads the lattice. `graphite.py` (sibling module) writes it. The relationship is Legendre: `grapheine` exposes `L(q, q̇)` — state and the rate at which it's measured — while `graphite` exposes `H(q, p)` — state and the obligations the measurements imply. Same `q`, conjugate momentum.

Three commands, each the dual of a grapheine read:

| read (grapheine) | dual write (graphite) |
|---|---|
| `unresolved` | `stub`       — create stub files for broken wikilinks |
| `orphans`    | `bond`       — suggest cross-links from tag-overlap |
| `properties` | `propagate`  — fill frontmatter keys that ≥N% of files share |

```bash
# dry-run by default — prints proposals, writes nothing
python3 graphite.py stub vault=my-vault limit=20
python3 graphite.py bond vault=my-vault k=2
python3 graphite.py propagate vault=my-vault min_share=0.5

# inspect the duality table
python3 graphite.py legendre

# --apply writes the proposals — gated to vaults under ~/Desktop/forge/ or ~/.claude/
python3 graphite.py stub vault=my-forge-vault --apply
```

Pencil on paper, mineral on lattice. Same chemistry, opposite gradient.

## License

MIT. © 2026 Logan Ross.

See `LICENSE` for full text.
