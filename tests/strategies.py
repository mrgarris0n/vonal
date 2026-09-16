"""Hypothesis strategies for valid plates.

Validity here is not cosmetic. A void cell with a non-zero variant or scale, and
a non-void cell whose form colour equals its ground, are both unrepresentable in
an image, so such plates would fail round-tripping for reasons that are not bugs.
"""

from hypothesis import strategies as st

from vonal.cell import Cell, Form, Plate


@st.composite
def cells(draw):
    form = draw(st.sampled_from(list(Form)))
    ground = draw(st.integers(0, 7))
    if form is Form.VOID:
        return Cell(Form.VOID, 0, 0, ground)
    variant = draw(st.integers(0, 7).filter(lambda v: v != ground))
    return Cell(form, variant, draw(st.integers(0, 7)), ground)


@st.composite
def plates(draw, max_side=4):
    width = draw(st.integers(1, max_side))
    height = draw(st.integers(1, max_side))
    rows = tuple(
        tuple(draw(cells()) for _ in range(width)) for _ in range(height)
    )
    return Plate(width, height, rows)
