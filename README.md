# Dirac's Graphene CLI tool for Knowledge Graphs

Graph-theoretic CLI for Obsidian vaults. Pure stdlib Python. No Obsidian app required.

> Your wikilink graph is a 2D lattice — notes as atoms, `[[links]]` as bonds. This tool exposes the lattice.

## What it does that other Obsidian CLIs don't

- **Runs without Obsidian.** No app, no plugin, no Node, no REST. Just Python and your vault directory.
- **Multi-vault stack analysis.** Treats your registered vaults as stacked sheets. Resolves cross-vault wikilinks. Reports cross-sheet bridges.
- **Graph math layer.** Degree distribution, triangles, clustering coefficient, girth, bipartite test, connected components, Fiedler value, Dirac-point candidates. Most Obsidian tools stop at backlinks/orphans.

## Install

Single file. Drop it on PATH or pip install (when published).

```bash
# Quick: just put the script on PATH
cp diracs_graphene.py ~/.local/bin/dirac && chmod +x ~/.local/bin/dirac

# Or, with pip
pip install --user .
```

Default vault: the first registered Obsidian vault. Override with `OBSIDIAN_VAULT=name` or `vault=name` per command.

## The intuition

Graphene — a single atomic layer of carbon, sp²-bonded into a hexagonal lattice — is a **bipartite honeycomb**: two interpenetrating sublattices A and B, where every A atom bonds to exactly three B atoms. At specific points in momentum space (the K and K' corners of the Brillouin zone), the energy bands touch with linear dispersion, producing massless 2D Dirac fermions. The math is the 2D Dirac equation.

A wikilink graph is the same shape, structurally:
- **Atoms = notes.** Each `.md` file is a node.
- **Bonds = wikilinks.** Each `[[link]]` is an edge.
- **Sublattices = bipartite 2-coloring.** If your graph is bipartite, the two color classes are the A and B sublattices.
- **Dirac points = high-degree nodes whose neighborhoods are balanced across sublattices.** These are the "pinholes" where the two halves of your knowledge graph touch.
- **Stack mode = twisted bilayer.** When you have multiple vaults, each is a sheet. Cross-vault wikilinks are the interlayer interaction term. Cross-sheet Dirac points are notes that bridge sheets.

This isn't metaphor. The Hamiltonian is identical: `H = -t Σ (a†b + h.c.)`, anticommuting with the sublattice operator, eigenvalues in `±E` pairs.

## Commands

### Basic vault ops

```bash
dirac vaults                                        # list registered vaults
dirac vault info=name                               # current vault info
dirac read file=note-name                           # print a note's content
dirac backlinks file=note-name [counts]             # what links to this note
dirac links file=note-name                          # what this note links to
dirac unresolved [verbose]                          # broken wikilinks
dirac orphans                                       # files with no incoming links
dirac aliases [file=note-name]                      # frontmatter aliases
dirac tags [counts] [sort=count]                    # tag distribution
dirac tag name=tagname [verbose]                    # files tagged with X
dirac search query="text" [path=dir] [limit=N]
dirac search:context query="text" [limit=N]         # with line context
dirac tasks [todo|done] [file=note-name|daily]
dirac properties file=note-name                     # frontmatter
dirac property:get name=key file=note-name
```

### Graph math

```bash
dirac graph degree [top=N]      # degree distribution + top hubs
dirac graph hubs [top=N]        # top-N nodes by degree
dirac graph triangles           # 3-cycles (honeycomb has 0)
dirac graph clustering          # global clustering coefficient
dirac graph girth               # shortest cycle (honeycomb=6)
dirac graph bipartite           # 2-color test; sublattice sizes
dirac graph components          # connected components
dirac graph density             # |E| / (|V|·(|V|-1)/2)
dirac graph dirac [top=N]       # Dirac-point candidates (pinholes)
dirac graph spectrum            # λ_max + Fiedler value (algebraic connectivity)
```

### Multi-vault stack

```bash
dirac health vault=*            # fingerprint across all leaf vaults
dirac moire                     # pairwise vault overlap (shared stems, Jaccard)
dirac graph dirac vault=*       # cross-sheet Dirac points (twisted-bilayer pinholes)
```

`vault=*` selects every leaf vault — vaults that don't contain another registered vault. Use `vault=every` to include parent/wrapper vaults.

## Reading the output

| Metric | Honeycomb expected | What it tells you |
|---|---|---|
| `triangles` | 0 | Triadic shortcuts violate honeycomb structure |
| `clustering` | 0.0 | Higher = your notes form cliques |
| `girth` | 6 | Shortest cycle. <6 means triangles or squares exist |
| `bipartite` | true | If false, no clean 2-coloring; sublattices not separable |
| `Fiedler λ_2` | "healthy" > 0.05 | Near zero = bottleneck; large = well-connected |
| `Dirac score` | high = strong bridge | `balance × degree` for single vault; `entropy × degree` for stack |

A real Obsidian vault is rarely a clean honeycomb. The metrics tell you how far it is from that ideal — and which notes anchor the structure.

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

Both `tags`/`tag` and `aliases`/`alias` keys are recognized.

## Resolution rules

- `[[link]]` resolves by stem (filename without `.md`), case-insensitive, with alias matching.
- `[[link|alias]]` and `[[link#section]]` and `[[link^block]]` all resolve to `link`.
- `[text](path/to/note.md)` markdown-style links count as wikilinks.
- In stack mode, same-vault matches win; cross-vault matches are the fallback.

## License

MIT. © 2026 Logan Ross.
