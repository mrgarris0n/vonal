"""Hypothesis strategies for plates.

Two distinct domains, named separately:

- `plates()`: *structurally valid* plates -- everything `Cell` and `Plate`
  themselves accept. Task 5's text round-trip (`parse`/`emit`) holds over
  this whole domain, because it only ever moves digits and never consults
  the instruction table.
- `loadable_plates()`: *loadable* plates -- the domain `decode()` accepts.
  In addition to structural validity, every non-void cell's `(form, variant)`
  must be a defined instruction per `isa.lookup`, since `decode()` is
  specified to reject an undefined pair with `LoadError`. Task 7's image
  round-trip uses this domain.

Validity here is not cosmetic. A void cell with a non-zero variant or scale, and
a non-void cell whose form colour equals its ground, are both unrepresentable in
an image, so such plates would fail round-tripping for reasons that are not bugs.
The same is true of a `plates()` cell whose (form, variant) is not a defined
instruction: `decode()` must reject it, so it has no meaningful image round trip.
"""

from hypothesis import strategies as st

from vonal import isa
from vonal.cell import Cell, Form, Plate


@st.composite
def cells(draw, loadable=False):
    form = draw(st.sampled_from(list(Form)))
    ground = draw(st.integers(0, 7))
    if form is Form.VOID:
        return Cell(Form.VOID, 0, 0, ground)
    variant = draw(
        st.integers(0, 7).filter(
            lambda v: v != ground and (not loadable or isa.lookup(form, v) is not None)
        )
    )
    return Cell(form, variant, draw(st.integers(0, 7)), ground)


@st.composite
def plates(draw, max_side=4):
    width = draw(st.integers(1, max_side))
    height = draw(st.integers(1, max_side))
    rows = tuple(
        tuple(draw(cells()) for _ in range(width)) for _ in range(height)
    )
    return Plate(width, height, rows)


@st.composite
def loadable_plates(draw, max_side=4):
    """Like `plates`, but every cell's (form, variant) is also a defined
    instruction, i.e. the domain `decode()` can actually load back."""
    width = draw(st.integers(1, max_side))
    height = draw(st.integers(1, max_side))
    rows = tuple(
        tuple(draw(cells(loadable=True)) for _ in range(width)) for _ in range(height)
    )
    return Plate(width, height, rows)
