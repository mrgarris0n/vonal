# Vonal

An esoteric programming language whose source form is an image.

A program is a grid of coloured geometric cells in the visual idiom of Victor
Vasarely. A cell's glyph selects an opcode, its form colour selects the variant,
and its size is both an immediate value and a writable data field. Running a
program can deform its own picture.

```
$ vonal run examples/hello.png
Hello, World!
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
```

## Notation

A `.vsr` file is a grid of four-character cell tokens laid out as the plate is:
`form`, `variant`, `scale`, `ground`.

A dot means the channel is zero. In the form position a dot is the void glyph
itself. `%plate WxH` is the only header, and it must match the grid.

```
%plate 3x1

o.57  +..7  ....
```

Push 5, print it, halt.

| Op | Token | Op | Token | Op | Token |
|---|---|---|---|---|---|
| push N | `o.N7` | dup | `%0.7` | gt | `D0.7` |
| push_acc N | `o1N7` | pop | `%1.7` | lt | `D1.7` |
| add | `#0.7` | swap | `%2.7` | eq | `D2.7` |
| sub | `#1.7` | over | `%3.7` | get | `@0.7` |
| mul | `#2.7` | roll | `%4.7` | put | `@1.7` |
| div | `#3.7` | turn | `v0.7` | out num | `+0.7` |
| mod | `#4.7` | turn if | `v1.7` | out char | `+1.7` |
| neg | `#5.7` | turn unless | `v2.7` | in num | `+2.7` |
| halt | `....` | | | in char | `+3.7` |

Replace `v` with `^`, `>` or `<` for the other three turn directions. `push_acc`
computes `v*8 + N`, so a row of discs spells a base-8 numeral.

The trailing `7` above is the ground colour, chosen because no variant reaches 7
and a non-void cell requires `variant != ground`. Any other value works.

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

`examples/vega.vsr` uses this: three cells push 5 and print it, and the other
253 are push instructions that never execute, their sizes a radial gradient that
reads as a bulging sphere. The other plates do the same with whatever cells the
eye never reaches. Void padding cannot carry a composition, since a void draws
nothing and must have scale 0, so the padding is unreached push discs instead.

`examples/kinetic.vsr` goes the other way and writes the field as it runs, so
`vonal trace` on it produces frames that differ. Every other plate traces to the
same image repeated.

## Examples

| Plate | Output |
|---|---|
| `countdown` | `54321` |
| `fibonacci` | first ten terms |
| `collatz` | trajectory of 6 |
| `vega` | `5`, inside a swell |
| `hello` | `Hello, World!` |
| `kinetic` | nothing; it draws a staircase into its own field |

```bash
.venv/bin/pytest
```

## Design

`docs/superpowers/specs/2026-09-16-vonal-design.md` has the full spec: the
encoding, the instruction table, error handling, and why the alternatives were
rejected.
