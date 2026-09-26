# Vonal specification

**Status:** implemented. Where this document turned out to be wrong it was
amended during execution, and each such place is called out inline rather than
quietly corrected. `docs/implementation-plan.md` is the record of that work.
**Date:** 2026-09-16, amended through 2026-09-17

## 1. Thesis

Vonal is a two-dimensional esoteric programming language whose source form is an
image in the visual idiom of Victor Vasarely. A program is a lattice of coloured
geometric cells — his *unités plastiques* — and the lattice is simultaneously the
instruction store and a writable data surface, so a running program visibly
deforms its own picture.

Two of Vasarely's signature moves are load-bearing rather than decorative:

- the **alphabet plastique** (a cell is a geometric form on a coloured ground,
  permuted combinatorially) supplies the instruction encoding;
- the **Vega swell** (a smooth field of varying cell size reading as a sphere)
  supplies the numeric field the program computes over.

The design rejected two alternatives. A pure *alphabet plastique* reading leaves
the lattice undeformed and amounts to Piet with a richer glyph set. A pure
deformation reading — where a cell's displacement from its ideal lattice position
*is* the instruction — fails on contact: a convincing swell is a smooth field, so
neighbouring cells carry near-identical displacements, meaning smooth plates
encode monotonous instruction gradients and real programs render as noise. The
aesthetic and the semantics are in direct opposition there.

## 2. Goals and non-goals

**Goals.** A Turing-complete language with defined semantics; a reference
interpreter in Python; a text notation that compiles to the canonical image and
disassembles back from it; exact, non-statistical decoding; plates that are
legible Op art rather than pixel noise.

**Non-goals.** Lattice-geometry warping in the renderer (§6 explains the
trade). A visual editor. Performance — nothing here is performance-bound.
Multiple palettes. A call stack or subroutines.

## 3. Execution model

**The plate.** A `W×H` lattice on a torus. The eye running off any edge
reappears on the opposite one. Vasarely's plates are tilings, so wrapping is
visually free and removes every edge case.

**The cell.** Four channels, three of them semantic:

| Channel | Role |
|---|---|
| `form` | opcode family |
| `form colour` | variant within the family, as an **offset from the ground** |
| `scale` | immediate value, `0–7` |
| `ground colour` | **no semantics** — free for composition |

The variant is not the figure's colour. It is `(figure − ground) mod 8`, so the
colour drawn is `(ground + variant) mod 8`. Offset 0 would paint the figure in
the ground's own colour and the cell would read as void, so variants run `1–7`
and a figure can never match its ground. That is an identity, not a rule the
model has to enforce, and it leaves ground with no constraints whatsoever.

Two things follow, and they are why the indirection is worth it. **Rotating a
cell's figure and ground together leaves the instruction unchanged**, so a whole
plate can be recoloured without altering a thing it does. And all eight palette
colours can be figures. Under the earlier absolute encoding the variant *was*
the figure colour, which meant only the six colours some opcode happened to use
could ever be drawn, every `push` was a black disc, and each cell forbade one
ground.

Freeing the ground colour is deliberate. It gives the artist an entire channel to
key the plate with, so any colour scheme can host any program, and logic can be
written before the plate is composed.

**And there is a second free channel, which the table above understates.** A
cell's `scale` is read by exactly two things: the `PUSH` family, which reads the
cell it is standing on, and a `get` aimed at that cell's coordinates. On every
other cell — every triangle, rhombus, square, cross, ring, half-disc, and every
void — the scale is as free as the ground. A plate that uses no `get` (which all
three shipped examples do not) has *one* semantically meaningful scale per disc
and nothing else, so the entire remaining scale field is available for
composition at zero cost to behaviour.

This is what makes §2's Op-art goal reachable rather than aspirational: a smooth
gradient of sizes across a body row, which is the *Vega* swell of §1, can be
laid over working code without touching a single opcode, variant or literal.

**The eye.** Position plus heading (N/E/S/W). It is the only locus of control.
Execution begins at `(0,0)` heading east, by convention — no metadata is stored
in the image. A triangle at `(0,0)` redirects it if another entry is wanted, so
nothing is lost.

Axes follow image convention: `x` increases rightward, `y` increases **downward**.
North is `-y`.

**Two stores, with different jobs:**

- **The stack** — unbounded integers. The actual compute surface, and the source
  of Turing-completeness. Invisible.
- **The field** — the grid's own `scale` channel, `W×H` cells of `0–7`, readable
  and writable at runtime. Bounded, and visible on any cell that draws a glyph:
  a write re-renders that cell at a new size.

  **A write to a void cell is valid and invisible.** Void cells are most of a
  real plate, so restricting the field to drawn cells would make it largely
  unaddressable and destroy its value as a data surface — the field is the whole
  grid. But a void cell draws nothing, so there is no glyph to resize: the value
  is stored, `get` reads it back, and the picture does not change. Two
  consequences follow and are accepted. A rendered frame is not a complete record
  of machine state, so a `trace` animation is a visualisation rather than a
  checkpoint one could resume from. And the visible-deformation claim above is a
  property of drawn cells, not a universal invariant.

The split is load-bearing. Computing on the bounded field alone would cap the
language at a linear-bounded automaton; computing on the stack alone would leave
the picture inert.

**The step.** Fetch the cell under the eye → opcode from form, variant from form
colour, immediate from scale → execute → advance one cell along the heading,
wrapping. Triangles rewrite the heading before the advance.

**Halting.** The eye enters a void cell. Non-termination is not an error;
`--max-steps` bounds it. Stopping at that bound is reported on stderr, because
a capped run and a finished one are otherwise indistinguishable from outside.

## 4. Forms and instruction set

Eleven glyphs: void, disc, square, rhombus, triangle in four rotations,
half-disc, ring, cross. The half-disc has one fixed orientation (flat side down);
it encodes comparison and needs no direction.

| Form | Glyph | Family | Variants (form colour index) |
|---|---|---|---|
| void | `.` | HALT | — (variant ignored) |
| disc | `o` | PUSH | `1` push `scale` · `2` pop `v`, push `v*8 + scale` |
| square | `#` | ARITH | `1` add `2` sub `3` mul `4` div `5` mod `6` neg |
| rhombus | `%` | STACK | `1` dup `2` pop `3` swap `4` over `5` roll |
| triangle | `^ > v <` | TURN | `1` always · `2` if top ≠ 0 · `3` if top = 0 |
| half-disc | `D` | COMPARE | `1` gt `2` lt `3` eq |
| ring | `@` | FIELD | `1` get · `2` put |
| cross | `+` | IO | `1` out num `2` out char `3` in num `4` in char |

Any `(form, variant)` pair not listed is a **load error**, not a no-op (§7).

A void cell carries no form, so neither its variant nor its scale is
representable in the image. **Both are defined to be 0** — `get` on a void cell
yields 0, and a non-zero variant or scale on a void cell is a compile error.
Without this rule the image could not round-trip a plate faithfully (§9): the
decoder has no way to recover a value the renderer never drew, so the model must
not admit one.

### 4.1 Operation semantics

Stack notation is `( before -- after )` with the top of stack rightmost.

- **push** `( -- scale )`. Variant `1` is `( v -- v*8 + scale )`, which makes a
  row of swelling discs a base-8 numeral spelled by the bulge itself.
- **add** `( a b -- a+b )`, **sub** `( a b -- a-b )`, **mul** `( a b -- a*b )`.
- **div** `( a b -- a//b )` and **mod** `( a b -- a%b )`, both using Python's
  floored semantics. `b = 0` is a runtime error.
- **neg** `( a -- -a )`.
- **dup** `( a -- a a )`, **pop** `( a -- )`, **swap** `( a b -- b a )`,
  **over** `( a b -- a b a )`.
- **roll** `( ... n -- ... )` pops `n`, then rotates the top `n` remaining
  elements by one position, moving the top element to the bottom of that group.
  `n < 0` or `n` exceeding the stack depth is a runtime error.
- **gt** `( a b -- a>b )`, **lt** `( a b -- a<b )`, **eq** `( a b -- a==b )`,
  each pushing `1` or `0`.
- **turn** sets the heading to the triangle's own rotation: `^` north, `>` east,
  `v` south, `<` west. Variants `1` and `2` pop their guard value.
- **get** `( x y -- field[y][x] )`. **put** `( v x y -- )`. Coordinates wrap
  modulo the grid (§7).
- **out num** `( v -- )` writes `v` in decimal. **out char** `( v -- )` writes
  `chr(v)`; a `v` outside the valid code-point range is a runtime error.
  **in num** `( -- v )` reads an integer, **in char** `( -- v )` reads one
  character's code point. Both push `-1` at EOF; malformed numeric input is a
  runtime error.

### 4.2 Turing-completeness

An unbounded integer stack, arithmetic, comparison and conditional branching via
guarded turns. This is the same argument Piet rests on. The field is bounded and
deliberately not load-bearing for computation — it is the kinetic surface.

## 5. Text notation (`.vsr`)

Source is a grid of fixed-width cell tokens, so the file visually *is* the plate.
Column alignment is the point; variable-width tokens would destroy the one
property that makes a two-dimensional language readable.

Each cell is four characters — `form`, `variant`, `scale`, `ground` — where `.`
in the variant, scale or ground position means the default, `0`. In the *form*
position `.` is not a default but the void glyph itself. Cells are separated by
whitespace; rows by newlines.

```
%plate 5x2

o157  +1.7  ....  ....  ....
....  ....  ....  ....  ....
```

That is: push 5, print it, halt. `o157` is a disc, variant 1, scale 5, ground 7,
drawn in colour `(7 + 1) mod 8 = 0`, black. `+1.7` is a cross, variant 1
(out num), scale 0, ground 7.

The grounds are free. Any value works here, 7 included, because no variant can
collide with a ground: offset 0 is not a variant.

**Canonical form: a dot means the channel is zero.** The parser accepts `0` and
`.` interchangeably in the variant, scale and ground positions, but `emit`
produces exactly one spelling — a dot for every zero channel, and for a void
cell's undrawn form, variant and scale. So `disassemble` returns source in the
same idiom a person writes, and `compile` followed by `disassemble` is
byte-identical rather than merely semantically equivalent.

The rule is uniform across all four positions deliberately. An earlier draft
dotted variant and scale but always printed ground as a digit, which broke
byte-identical round-tripping for any coloured shape on ground 0 — `Cell`'s own
default — and let the void and non-void branches of the emitter drift apart.
Spelling it as one rule rather than two is what keeps them together.

`%plate WxH` is a redundancy check — a mismatch with the actual grid is a compile
error. It is the only header. There is no `%palette` directive, because there is
only one palette, and no `%entry`, because entry is fixed by convention (§3).

**Line sigils collide with the glyph alphabet, so the grammar disambiguates them
explicitly.** `#` is the square and `%` the rhombus, so a naive "lines starting
with `#` are comments, lines starting with `%` are directives" rule silently
discards a row whose first cell is a square and rejects one whose first cell is a
rhombus. The rule is therefore:

- a line is a **directive** iff it matches `^%plate\s+(\d+)x(\d+)\s*$` exactly;
- a line is a **comment** iff, stripped, it is exactly `#` or begins with `# `;
- every other non-blank line is a grid row.

Two diagnostic costs follow and are accepted: `#comment` without a space is a
parse error rather than a comment, and a mistyped directive such as `%plat 3x1`
is reported as a malformed cell rather than as a bad directive. Moving comments
to a sigil outside the glyph alphabet would not help — `%` is a glyph too, so the
exact-match directive rule is needed either way.

Defaulting carries real weight. Void cells are most of a real plate, and `....`
costs nothing while keeping columns square. Because ground colour has no
semantics, logic can be written with every ground left `.` and the colour field
painted in afterwards without touching behaviour.

**Loops come from wrapping.** A row is a torus, so a row that ends without a turn
re-enters at its own left edge. The idiom is a body row that wraps, containing a
guarded triangle that deflects the eye into an exit row when the guard fails.

**Both directions.** `compile` takes `.vsr` → PNG; `disassemble` takes PNG →
`.vsr`. The PNG is the canonical program; the text is scaffolding.

## 6. Image encoding

**Rigid lattice, 64×64 px cells.** The swell lives in form size, not in warped
cell boundaries. This is an art-historical judgement as much as an engineering
one: a constant grid of discs whose radii follow a smooth falloff already reads
as a sphere, which is how much of Vasarely's output works. Warping the lattice
would buy a marginally purer *Vega* at an order of magnitude more decoder
complexity.

The image is therefore fully self-describing. Grid size is
`width/64 × height/64`. No PNG metadata chunks — they strip on resave, which
would undermine the claim that the picture is the program.

**Palette `vonal-8`:**

| | | | |
|---|---|---|---|
| `0` `#111111` | `1` `#F2F0E9` | `2` `#2B4EA2` | `3` `#4FA3D1` |
| `4` `#1E9B6B` | `5` `#F2C230` | `6` `#D64530` | `7` `#7B4B9B` |

**Geometry.** A form is inscribed in a square of side `L(s) = 8 + 7s` pixels,
`s ∈ 0..7`, giving 8–57 px, centred in the 64 px cell at floored offset
`(64 - L)/2`. The bound matters: `L(7) = 50` leaves at least 7 px of ground on
every side, so a non-void cell always shows exactly two colours. Ring thickness
is `max(2, L//4)`; cross arm thickness is `max(2, L//3)`.

**Hard edges, no anti-aliasing.** Correct for hard-edge abstraction, and it is
what makes decoding exact rather than statistical. The aesthetics and the
engineering want the same thing.

**Decoding.** A cell showing a single colour is void, and is recognised by that
test alone — void is not in the template table, since it renders identically at
every scale and would otherwise defeat the injectivity assertion below. The
remaining 80 `(form, scale)` templates (10 non-void forms × 8 scales) are
rendered once at startup with the two colours normalised to 0 and 1, and keyed in
a dict by template bytes. Decoding a non-void cell is: read its 64×64 block, map
its two distinct colours to palette indices by exact RGB, normalise, one dict
lookup. O(1) per cell, no numpy, and
`render` remains the single source of truth for what a glyph looks like — there
is no separate recognition code to drift out of sync.

Template-table construction **asserts injectivity**: if any two `(form, scale)`
pairs ever render identically, that is a build-time failure, not a silent
ambiguity at decode time.

**Animation falls out.** A `put` mutates a cell's scale, so the interpreter can
emit a frame per step, or one every N steps, and dump a run as an animation.
It can also outline the cell under the eye, in the margin no glyph reaches;
such a frame pictures the machine rather than the plate, and does not decode.

## 7. Error handling

Three phases, each failing completely before the next begins.

**Compile** (`.vsr` → PNG): malformed tokens, ragged rows, out-of-range digits,
`%plate` mismatch, **a non-void cell whose form colour equals its ground
colour**, and **an undefined `(form, variant)` pair anywhere on the plate**.
Reported with line and column where the token position is known, and by grid
cell otherwise.

The last two belong here rather than at load, for opposite reasons. Equal
colours *cannot* be detected at load — such a cell renders as, and decodes as,
void, which is precisely why it is forbidden — so the rule is enforceable only
against the text. An undefined opcode, by contrast, is detectable at load and is
also rejected there; compile must reject it too, including on cells the eye
never visits. Otherwise `compile` would write a canonical artefact that `decode`
refuses, exit successfully, and leave the text and the image accepting different
sets of programs. They accept the same set, and keeping them aligned is
compile's job.

**Load** (PNG → program): image dimensions not a multiple of 64; more than
65536 cells; a cell with more than two distinct colours; a colour outside
`vonal-8`; no matching `(form, scale)` template; an undefined
`(form, variant)` pair.

The cell ceiling is 256×256, which is 16384 pixels square. It exists because a
cell is 64 pixels square, so a plate is a legitimately enormous image and trips
Pillow's decompression-bomb guard at 89 megapixels: a 170×165 plate is 115.
Removing the guard is wrong, since a plate is not always one you wrote and a
small PNG that inflates to gigabytes is a real attack, so it is raised to a
bound a plate can justify. Past it a plate is refused, not merely warned
about.

Validating variants at load makes opcode validity a whole-program static check: a
plate that loads cannot contain an invalid instruction.

This yields an invariant worth stating plainly. **`put` writes the scale channel,
and scale never participates in opcode selection.** Runtime mutation changes
immediates but can never manufacture an instruction. Unlike Befunge's `p`,
self-modification here is confined to data, and a program that loads stays valid
for its entire run.

**Runtime:** stack underflow; division or modulo by zero; `roll` with a negative
or oversized `n`; `put` with a value outside `0–7`; `out char` with an invalid
code point; malformed numeric input. All halt and name the offending cell.

**The governing rule: wrapping is topological, never numeric.** Positions wrap —
the eye on the torus, and `get`/`put` coordinates modulo the grid, so field
addressing has no out-of-range case at all. Values never wrap. A `put` of 9 is a
bug, not a 1; silently truncating it would make broken plates look like working
ones, which is the same reason undefined variants are rejected rather than
no-oped.

Errors report the grid cell `(x, y)`. Because the notation is itself a grid, that
maps back to a `.vsr` token positionally, with no sourcemap needed.

Exit codes: `0` on clean halt or a run stopped by `--max-steps`, non-zero on any
error. The cap is a bound the user asked for, not a fault.

## 8. Architecture

`Plate` is the hub — a `W×H` grid of `Cell(form, variant, scale, ground)`. Text
and image are two *representations* of it, and neither module knows the other
exists. Every conversion passes through the centre, which is what makes the
round-trip properties in §9 meaningful.

```
vonal/
  palette.py    8 colours, exact RGB ↔ index
  cell.py       Cell, Form enum, Plate
  isa.py        (form, variant) → operation; validity
  notation.py   .vsr ↔ Plate
  render.py     Plate → PNG; the (form, scale) template generator
  decode.py     PNG → Plate
  machine.py    eye, stack, field, step loop
  errors.py     error types carrying cell coords
  cli.py        compile / disassemble / run / trace
```

Dependencies: Pillow, pytest, hypothesis. Nothing else.

## 9. Testing

Test-driven throughout, in descending order of confidence bought:

1. **Round-trip properties** (Hypothesis). Generate arbitrary valid `Plate`s and
   assert `vsr → Plate → vsr` and `Plate → PNG → Plate` are both identity. This
   is what proves encode and decode are genuine inverses rather than merely
   agreeing today.

   The two round trips have **different domains**, and conflating them breaks the
   image property. A *structurally valid* plate is one `Cell` accepts: void cells
   at variant and scale 0, and no non-void cell whose form and ground colours
   match. A *loadable* plate is additionally one whose every cell is a defined
   instruction per §4's table. The text round trip holds over all structurally
   valid plates, because `parse` and `emit` move digits and never consult the
   instruction table. The image round trip holds only over loadable plates,
   because §7 requires `decode` to reject an undefined `(form, variant)` pair —
   a plate it must reject has no meaningful round trip. Only 34 of the 80
   non-void pairs are defined, so a generator that ignores this produces
   failures that are not defects.
2. **ISA unit tests.** Table-driven, one per operation, asserting effects on
   stack, field and eye in isolation.
3. **Golden programs.** A corpus of `.vsr` with expected stdout, run through the
   CLI: countdown, Fibonacci, Collatz.
4. **Error tests.** One per class in §7, asserting the reported coordinate.

## 10. Decided tunables

Recorded so they are not relitigated silently:

- **Scale quantisation is 8 steps.** Sixteen would render a smoother swell and
  halve glyph legibility at a glance. Eight still reads as smooth at arm's
  length.
- **Edges wrap rather than halting.** Consistent with his tiling plates, and it
  makes loops fall out of the topology.
- **Cell size is fixed at 64 px.** Making it variable would require metadata in
  the image, which §6 rules out.
