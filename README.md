# Dirac's Graphene CLI tool for Knowledge Graphs

**Graph-theoretic CLI for any folder of `[[wikilinked]]` markdown.**

Works on Obsidian vaults, Logseq graphs, Roam exports, Foam, Dendron, Quartz, Hugo content trees, Notion `.md` exports, plain Zettelkasten — anything with `[[name]]` or `[text](file.md)` references between markdown files.

Pure stdlib Python. No app, no plugin, no daemon, no REST.

> Your knowledge graph is a 2D lattice — notes as atoms, `[[links]]` as bonds. This tool exposes the lattice.

## Why this exists

Most knowledge-graph CLIs stop at backlinks and orphans. `graphene` adds the layer that isn't elsewhere:

- **Cross-source wikilink resolution.** Point it at multiple folders (or all your registered Obsidian vaults at once) and links resolve across sources. Genuinely uncontested — Obsidian itself doesn't support cross-vault internal links.
- **Spectral & topological metrics.** Girth, bipartite test with sublattice sizes, Fiedler value (algebraic connectivity), Dirac-point candidates. None of these are exposed by the official Obsidian CLI, by `obsidiantools`, by `obsidian-cli-ops`, or by `obra/knowledge-graph`.
- **No app required.** Reads your folder directly. Doesn't launch Obsidian, doesn't need a plugin, doesn't need Node, doesn't need a REST endpoint.

## Quick start

```bash
# install (single command, no clone needed)
pip install --user git+https://github.com/loross14/diracs-graphene

# or from a clone
git clone https://github.com/loross14/diracs-graphene
cd diracs-graphene
pip install --user .
```

> If `graphene` isn't found after install, ensure `~/.local/bin` is on your `PATH`.
> Windows: `pip install` is the recommended path; the POSIX-style copy/`chmod` recipe won't work on PowerShell/cmd.

Three commands, three outputs:

```bash
$ graphene vaults
gitmoney
notes
research

$ graphene health vault=notes
[GRAPHENE] notes: nodes=512 edges=1834 ⟨k⟩=7.16 orphans=89 isolates=42 unresolved=27 tags=63 bipartite=false A/B=204/308

$ graphene graph degree vault=notes top=5
nodes=512 edges=1834 mean_deg=7.165 median_deg=4 max_deg=78
isolated=42 deg=1:91 deg=2:67 deg=3:48 deg≥10:96
--- top-5 hubs ---
    78  index.md
    63  daily/2026-04-28.md
    51  reading-list.md
    44  projects/_moc.md
    37  people.md
```

## Pointing graphene at any folder

`graphene` works on any directory of markdown — Obsidian registry not required:

```bash
# any folder
graphene health vault=/path/to/your/notes
graphene graph degree vault=~/zettelkasten

# Obsidian users: shortcut by registered name
graphene health vault=gitmoney

# multi-source stack (every leaf vault registered with Obsidian)
graphene health vault=stack

# default: set GRAPHENE_VAULT (or OBSIDIAN_VAULT for backwards compat)
export GRAPHENE_VAULT=/path/to/your/notes
graphene health
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
- **Stack mode = bilayer-style overlay.** Multiple folders/vaults stacked; cross-source wikilinks become interlayer bonds.

**Same chiral symmetry, not the same lattice.** Any bipartite graph carries the A↔B sublattice anticommutation, so spectra come in ±E pairs. *Real* Dirac cones — the linear-dispersion crossings — are a momentum-space feature of the periodic honeycomb that wikilink graphs don't have. We use "Dirac point" as the structural proxy: a high-degree node whose neighborhood is balanced across sublattices. Right shape, not the literal cone.

Same caveat for stack mode: the twisted-bilayer-graphene analogy is shape-of-the-thing, not a moiré / magic-angle calculation. The score is Shannon entropy over sheet-membership, weighted by degree.

> If you don't care about the chemistry, skip to **Commands** — the math works regardless.

## Commands

### Basic

```bash
graphene vaults                                        # list registered Obsidian vaults
graphene vault info=name                               # current source info
graphene read file=note-name                           # print a note's content
graphene backlinks file=note-name [counts]             # what links to this note
graphene links file=note-name                          # what this note links to
graphene unresolved [verbose]                          # broken wikilinks
graphene orphans                                       # files with no incoming links
graphene aliases [file=note-name]                      # frontmatter aliases
graphene tags [counts] [sort=count]                    # tag distribution
graphene tag name=tagname [verbose]                    # files tagged with X
graphene search query="text" [path=dir] [limit=N]
graphene search:context query="text" [limit=N]         # with line context
graphene tasks [todo|done] [file=note-name|daily]
graphene properties file=note-name                     # frontmatter
graphene property:get name=key file=note-name
```

### Graph math

```bash
graphene graph degree [top=N]      # degree distribution + top hubs
graphene graph hubs [top=N]        # top-N nodes by degree
graphene graph triangles           # 3-cycles (honeycomb has 0)
graphene graph clustering          # average local clustering coefficient
graphene graph girth               # shortest cycle (honeycomb=6)
graphene graph bipartite           # 2-color test; sublattice sizes
graphene graph components          # connected components
graphene graph density             # |E| / (|V|·(|V|-1)/2)
graphene graph dirac [top=N]       # Dirac-point candidates (bridges)
graphene graph spectrum            # λ_max + Fiedler value (algebraic connectivity)
```

### Multi-source stack

```bash
graphene health vault=stack        # fingerprint across leaf vaults
graphene moire                     # pairwise overlap (shared stems, Jaccard)
graphene graph dirac vault=stack   # cross-source Dirac points
```

`vault=stack` is the safe glob-free form of `vault=*`. Selects every leaf vault registered with Obsidian (vaults that don't contain another registered vault). Use `vault=every` to include parent/wrapper vaults too.

If your shell expands `*` (zsh/bash usually do), quote it: `vault='*'`.

## Reading the output

| Metric | Honeycomb expected | What it tells you |
|---|---|---|
| `triangles` | 0 | Triadic shortcuts violate honeycomb structure |
| `avg_local_clustering` | 0.0 | Higher = your notes form cliques |
| `girth` | 6 | Shortest cycle. <6 means triangles or squares exist |
| `bipartite` | true | If false, no clean 2-coloring; sublattices not separable |
| `Fiedler λ_2` | "healthy" > 0.05 | Near zero = bottleneck; large = well-connected |
| `Dirac score` | high = strong bridge | `balance × degree` (single) or `entropy × degree` (stack) |

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
| `vault not found` | Pass an explicit path: `graphene health vault=/abs/path/to/folder`. Or check `graphene vaults` to list registered Obsidian vaults. |
| `(no vaults registered — is Obsidian installed?)` | You don't have an Obsidian config. Use `vault=/path/to/folder` instead of relying on the registry. |
| `command not found: graphene` | Ensure your install location (e.g. `~/.local/bin`) is on `PATH`. Try `python3 -m diracs_graphene <command>` to bypass. |
| Linux Flatpak / Snap users see no vaults | Auto-detection covers native paths only. Pass `vault=/path/to/folder` directly. |
| `graphene graph spectrum` reports negative Fiedler | Phase-1 power iteration undershot λ_max. Increase `iters=200` or run on a smaller subgraph (`vault=specific-folder`). |

## What this isn't

- **Not affiliated with `graphene` (graphene-python)** — the GraphQL library on PyPI. We're a *console script* named `graphene`; they're a Python library you import as `import graphene`. No collision at the binary layer (graphene-python doesn't install a CLI), but if you've never heard of either before today, the names overlap. Different ecosystem, different namespace.
- **Not affiliated with `DIRAC`** — the HEP distributed-computing framework on PyPI (`pip install dirac`). They ship hundreds of `dirac-*` console scripts; we ship a single `graphene` for graph queries.
- **Not affiliated with `dirac-graph`** — the computational spectral geometry library by `pulquero`. Adjacent territory, different scope.
- **Not affiliated with the `obsidian-graphene` Obsidian plugin** by `suniyao` (vector-embedding graph view).
- **Not affiliated with `libgraphene`** — the GNOME math/geometry library shipped via Homebrew. They install library files only, no `graphene` binary.

## Roadmap

`graphene` is the **read-side** tool — it observes the lattice. A planned companion `graphite` will be the **write-side**: stub unresolved wikilinks, suggest cross-sheet bonds, propagate frontmatter conventions. Pencil on paper, mineral on lattice. Same chemistry, opposite gradient.

## License

MIT. © 2026 Logan Ross.

See `LICENSE` for full text.
