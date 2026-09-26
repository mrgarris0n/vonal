# Vonal

[![tests](https://github.com/mrgarris0n/vonal/actions/workflows/ci.yml/badge.svg)](https://github.com/mrgarris0n/vonal/actions/workflows/ci.yml)

An esoteric programming language whose source form is an image.

A program is a grid of coloured geometric cells in the visual idiom of Victor
Vasarely. A cell's glyph selects an opcode, its form colour selects the variant,
and its size is both an immediate value and a writable data field. Running a
program can deform its own picture.

```
$ vonal run examples/hello.png
Hello, World!

$ echo 27 | vonal run examples/collatz-in.vsr
27 82 41 124 62 31 94 ... 8 4 2 1
```

That is the PNG being decoded and executed. The picture is the program.

## Install

Requires Python 3.11 or later.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Commands

```bash
vonal compile     src.vsr out.png     # text source to canonical image (.png only)
vonal disassemble in.png [out.vsr]    # image back to text
vonal run         plate [--max-steps N]   # accepts .vsr or .png
vonal trace       plate outdir/       # one PNG frame per step
vonal trace       plate anim.gif     # or an animated GIF (--frame-ms N)
vonal trace       plate anim.gif --every N   # one frame every N steps, plus the last
vonal trace       plate anim.gif --eye       # outline the cell the eye runs next
vonal --version                       # the installed version
```

## Notation

A `.vsr` file is a grid of four-character cell tokens laid out as the plate is:
`form`, `variant`, `scale`, `ground`.

A dot means the channel is zero. In the form position a dot is the void glyph
itself. `%plate WxH` is the only header, and it must match the grid.

```
%plate 3x1

o157  +1.7  ....
```

Push 5, print it, halt.

| Op | Token | Op | Token | Op | Token |
|---|---|---|---|---|---|
| push N | `o1N7` | dup | `%1.7` | gt | `D1.7` |
| push_acc N | `o2N7` | pop | `%2.7` | lt | `D2.7` |
| add | `#1.7` | swap | `%3.7` | eq | `D3.7` |
| sub | `#2.7` | over | `%4.7` | get | `@1.7` |
| mul | `#3.7` | roll | `%5.7` | put | `@2.7` |
| div | `#4.7` | turn | `v1.7` | out num | `+1.7` |
| mod | `#5.7` | turn if | `v2.7` | out char | `+2.7` |
| neg | `#6.7` | turn unless | `v3.7` | in num | `+3.7` |
| halt | `....` | | | in char | `+4.7` |

Replace `v` with `^`, `>` or `<` for the other three turn directions. `push_acc`
computes `v*8 + N`, so a row of discs spells a base-8 numeral.

The trailing `7` is the ground colour. Any value works, including 7: `ground`
is unconstrained.

The variant is not a colour. It is the figure colour's **offset** from the
ground, so the colour drawn is `(ground + variant) mod 8`. Offset 0 would paint
the figure in the ground's own colour, which is why variants run 1 to 7 and why
a figure can never match its ground: that is now an identity rather than a rule.

The consequence is worth the indirection. Rotating a cell's figure and ground
together leaves the instruction untouched, so a whole plate can be recoloured
without changing a thing it does. All eight colours can be figures, where the
old absolute encoding could only ever draw six of them and made every `push` a
black disc.

## How it runs

The eye starts at `(0,0)` heading east and advances one cell per step. The plate
is a torus, so running off any edge wraps. Headings persist until a triangle
changes them, which is the most common authoring mistake: a body row entered
from above is heading south, not east.

Two stores, with different jobs. An unbounded integer stack does the computing.
The grid's own scale channel is a bounded, writable field of 0 to 7 per cell,
readable and writable at runtime, and visible: a write re-renders that cell at a
new size.

Execution halts on a void cell.

## Composition

Two channels are free, which is what lets code and picture coexist.

`ground` has no semantics anywhere. `scale` is read only by the push family on
the cell the eye stands on, and by a `get` aimed at that cell, so on every other
cell it is free too.

`examples/orb.vsr` uses this: six cells push 5 and print it with a newline,
and the other 250 are push instructions that never execute, their sizes a
radial gradient that reads as a bulging sphere. Its ground is keyed in three
concentric bands, and the figures follow them because the variant is an offset.
The other plates do the same with whatever cells the eye never reaches. Void
padding cannot carry a composition, since a void draws nothing and must have
scale 0, so the padding is unreached push discs instead.

`examples/vortex.vsr` has no unreached cells at all. It is a square spiral of
triangles, and the eye runs every one of its 225 cells exactly once before
halting on the void at the centre, so the picture is a diagram of its own
route. Most of the triangles do nothing: a turn that restates the heading the
eye already has is a no-op, so a side of a ring can be all triangles and still
be a straight run, and only the corners and a seam down the diagonal actually
turn. The first few cells of each ring are discs and a cross instead, and
between them the seven rings print `vortex`. A trace of the field alone would
show nothing happen here, so `examples/vortex.gif` is traced with `--eye`
(and `--frame-ms 60`), which outlines the cell the eye runs next in every frame.

`examples/kinetic.vsr` goes the other way and writes the field as it runs, so
`vonal trace` on it produces frames that differ. `examples/kinetic.gif` is that
trace animated: runs of identical frames are collapsed into one held
proportionally longer, so the file stays small without the timing changing.

`examples/bubble.vsr` is the same trick doing real work. Row 7 holds eight
values as the sizes of eight discs, and the program bubble sorts that row of
the field in place, so the picture rearranges itself into a rising staircase
while it runs. `examples/bubble.gif` is the sort. Retracing it wants
`--max-steps 2000 --frame-ms 15`. The cap is the one that matters: the plate
runs 1801 steps against a `trace` default of 1000, and stopping at the cap
says so rather than quietly handing you an animation that ends mid-sort. The
frame time is only the speed the shipped GIF plays at.

`examples/swell.vsr` computes its composition instead of carrying one. It
ships flat — 225 squares in rows 5 to 19, every one the same size — and the
program walks all of them and writes a radial falloff into their scales, so
the lattice inflates into a Vega-series bulge as it runs.
`examples/swell.gif` is that inflation; retracing it wants
`--max-steps 14000`. The falloff is `7 - (dx*dx + dy*dy)/14`, and it belongs
to this language twice over. `dx*dx` is never negative, so no absolute value
is needed, and an `abs` would cost a comparison, which in a grid is a
physical detour. And the corner comes to 98 with `98/14 = 7`, so the result
lands in 0 to 7 by construction — `put` rejects anything outside that range,
so a formula that cannot leave it is what lets the body run straight through
without a single branch. Every square in the field is the same instruction,
`add`. Only the ground alternates, and the figure alternates with it because
the variant is an offset: one instruction, two colours. It is the inverse of
`orb`, where the swell is authored and the program ignores it.

`examples/inversion.vsr` is a chequer that turns itself inside out by
resizing. Every square is `div`, variant 4, on alternating blue and red
grounds, and offset 4 is the one that makes each square's figure exactly its
neighbours' ground: `2 + 4 = 6` and `6 + 4 = 2`. A small square reads as its
ground and a full-size one as its neighbour's, so the plate ships as a cone of
sizes with its centre already inverted. The program reads each size with
`get` and writes back `7 - s`, the cone becomes a bowl, and
`examples/inversion.gif` shows the inversion moving from the centre to the
rim; retracing it wants `--max-steps 8100`. No colour changes anywhere, and no
opcode can change one.

`examples/ripple.vsr` moves its rings outward. Round rings would need a
square root, which the language does not have, so they are authored, and only
the step is computed: every disc sits at one of eight points in the cycle
`0 2 4 6 7 5 3 1`, and each pass moves every disc one point along it. The cycle
rises through the evens and falls through the odds, so no size repeats and a
disc's size alone says where it is in the wave. The step is a lookup table,
and the table is eight discs in row 2 that the program reads with `get`:
reshape them and the wave changes, and write the cycle run forward there
(`2 0 4 1 6 3 7 5`) and the ripples fall inward. Every pass is exactly 10260
steps, so `examples/ripple.gif` is traced with `--every 10260 --frame-ms 120`,
one frame per finished pass; seven passes leave it one step short of where it began, so the
animation loops without a seam.

`examples/tally.vsr` is what the offset encoding buys. Every cell is its
own figure and ground pair, keyed by `(x + y) mod 8`, so all eight colours
appear as grounds and all eight as figures. The figures follow the ground
diagonally because the variant is an offset, and where they break the diagonal
is where an instruction sits: you choose which channel carries the clean
pattern, and the other one records the code. It prints the sum of all 384
scales, its own loop included, so resizing any glyph moves the number.

`examples/mirror.vsr` inverts the idea. A `get` points at the swell, so those
scales stop being composition and become the program's input: it prints the
profile of its own sphere. The same pixels are decoration or data depending only
on whether anything reads them.

That is the only self-reference available. The field is built from the scale
channel alone and no opcode exposes a cell's form, variant or ground, so a
program can read its own data but never its own code.

That rules out introspection, not quines. `examples/quine.vsr` prints itself,
byte for byte:

```bash
$ vonal run examples/quine.vsr | diff - examples/quine.vsr && echo identical
identical
```

It carries no comment header, because a comment is not part of the canonical
form and no plate could reproduce one.

It works because `get` makes the data self-describing. Rows 5 to 95 are all
push discs on a black ground, so each one's token is `o1<scale>.` and the
program can print it by reading its own scale. The ground has to be uniform:
it is the one channel no opcode can read, so the printer emits that last
character from a literal and could not follow a ground that varied. Keying it
cell by cell, which is what every other plate now does, is the one thing a
quine forbids. Only rows 0 to 4, the program itself, cannot be
derived that way, so their text is encoded in those same scales as base-7
digits, three cells per character, stored as 1 to 7 so no data cell is ever a
dot. One pass decodes the header and the program, a second generates
everything below it.

Those cells are therefore read twice, once as themselves and once as digits,
which is the whole trick and also its cost: resize a disc in the overlap and
the plate stops describing itself.

## Examples

| | Plate | Output |
|---|---|---|
| <img src="docs/previews/countdown.png" width="200" height="86" alt="countdown"> | `countdown` | `54321` |
| <img src="docs/previews/fibonacci.png" width="200" height="43" alt="fibonacci"> | `fibonacci` | first ten terms |
| <img src="docs/previews/collatz.png" width="200" height="33" alt="collatz"> | `collatz` | trajectory of 6 |
| <img src="docs/previews/collatz-in.png" width="200" height="33" alt="collatz-in"> | `collatz-in` | trajectory of whatever you pipe in |
| <img src="docs/previews/orb.png" width="120" height="120" alt="orb"> | `orb` | `5`, inside a swell |
| <img src="docs/previews/hello.png" width="150" height="120" alt="hello"> | `hello` | `Hello, World!` |
| <img src="docs/previews/kinetic.png" width="180" height="120" alt="kinetic"> | `kinetic` | nothing; it draws a staircase into its own field |
| <img src="docs/previews/mirror.png" width="138" height="120" alt="mirror"> | `mirror` | the profile of its own swell, read back with `get` |
| <img src="docs/previews/prime.png" width="200" height="109" alt="prime"> | `prime` | `1` or `0`, deciding a piped-in number |
| <img src="docs/previews/span.png" width="200" height="27" alt="span"> | `span` | the largest of three piped-in characters, and its negation |
| <img src="docs/previews/bubble.png" width="200" height="67" alt="bubble"> | `bubble` | `0 1 2 3 4 5 6 7`, sorted out of its own picture |
| <img src="docs/previews/swell.png" width="90" height="120" alt="swell"> | `swell` | nothing; it inflates its own flat lattice into a sphere |
| <img src="docs/previews/tally.png" width="180" height="120" alt="tally"> | `tally` | `613`, the total of its own glyph sizes |
| <img src="docs/previews/vortex.png" width="120" height="120" alt="vortex"> | `vortex` | `vortex`, while the eye runs every cell once |
| <img src="docs/previews/inversion.png" width="102" height="120" alt="inversion"> | `inversion` | nothing; it turns its own bulge inside out |
| <img src="docs/previews/ripple.png" width="109" height="120" alt="ripple"> | `ripple` | nothing; its rings travel outward, one step per pass |
| <img src="docs/previews/quine.png" width="72" height="120" alt="quine"> | `quine` | its own source, byte for byte |

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy
```

## Design

`docs/spec.md` has the full specification: the
encoding, the instruction table, error handling, and why the alternatives were
rejected.

## Licence

MIT. See `LICENSE`. The plates are generated from the formulas in this
repository, not derived from any particular artwork.

Victor Vasarely's name appears here to say what the visual idiom is. This
project is not affiliated with, endorsed by, or connected to the Vasarely
estate or the Fondation Vasarely.
