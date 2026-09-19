"""The plate data model. Text and image are two representations of Plate."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Heading(enum.Enum):
    N = (0, -1)
    E = (1, 0)
    S = (0, 1)
    W = (-1, 0)


class Form(enum.Enum):
    VOID = "."
    DISC = "o"
    SQUARE = "#"
    RHOMBUS = "%"
    TRIANGLE_N = "^"
    TRIANGLE_E = ">"
    TRIANGLE_S = "v"
    TRIANGLE_W = "<"
    HALF_DISC = "D"
    RING = "@"
    CROSS = "+"

    @property
    def heading(self) -> Heading | None:
        """The heading a TURN sets, or None for non-triangles."""
        return _TRIANGLE_HEADINGS.get(self)


_TRIANGLE_HEADINGS = {
    Form.TRIANGLE_N: Heading.N,
    Form.TRIANGLE_E: Heading.E,
    Form.TRIANGLE_S: Heading.S,
    Form.TRIANGLE_W: Heading.W,
}


@dataclass(frozen=True)
class Cell:
    """One unite plastique. `variant` is the form colour: one channel, one job."""

    form: Form
    variant: int = 0
    scale: int = 0
    ground: int = 0

    def __post_init__(self) -> None:
        for name in ("variant", "scale", "ground"):
            value = getattr(self, name)
            if not 0 <= value <= 7:
                raise ValueError(f"{name} must be 0..7, got {value}")
        if self.is_void:
            # Neither channel is drawn for a void cell, so the decoder could never
            # recover a non-zero value. The model must not admit one.
            if self.variant or self.scale:
                raise ValueError("a void cell must have variant 0 and scale 0")
        elif not 1 <= self.variant <= 7:
            # The variant is the figure colour's offset from the ground, so
            # offset 0 would paint the figure in the ground's own colour and
            # the cell would render as void. Excluding it is what makes
            # "a figure never matches its ground" an identity rather than a
            # rule, and leaves ground with no constraints at all.
            raise ValueError(f"a non-void cell needs variant 1..7, got {self.variant}")

    @property
    def is_void(self) -> bool:
        return self.form is Form.VOID

    @property
    def figure(self) -> int:
        """The palette index the glyph is painted in.

        The variant is stored as an offset from the ground rather than as a
        colour, so the same instruction can wear any of the eight colours
        depending on what it sits on. Rotating a cell's figure and ground
        together therefore leaves the program identical, which is what lets a
        whole plate be recoloured without touching what it does.
        """
        return (self.ground + self.variant) % 8


@dataclass(frozen=True)
class Plate:
    width: int
    height: int
    cells: tuple[tuple[Cell, ...], ...]  # indexed [y][x]

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("a plate must have at least one cell")
        if len(self.cells) != self.height or any(len(r) != self.width for r in self.cells):
            raise ValueError("cells do not match the declared width and height")

    def at(self, x: int, y: int) -> Cell:
        """Read a cell. The plate is a torus, so any coordinate is in range."""
        return self.cells[y % self.height][x % self.width]

    def replaced(self, x: int, y: int, cell: Cell) -> Plate:
        rows = [list(row) for row in self.cells]
        rows[y % self.height][x % self.width] = cell
        return Plate(self.width, self.height, tuple(tuple(r) for r in rows))
