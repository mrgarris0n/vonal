"""The .vsr text notation. The grid of tokens is laid out as the plate is."""

from __future__ import annotations

import re

from vonal.cell import Cell, Form, Plate
from vonal.errors import CompileError

_HEADER = re.compile(r"^%plate\s+(\d+)x(\d+)\s*$")
_GLYPHS = {form.value: form for form in Form}


def _digit(char: str, line: int, col: int, name: str) -> int:
    if char == ".":
        return 0
    if not char.isdigit() or not 0 <= int(char) <= 7:
        raise CompileError(line, col, f"{name} must be '.' or a digit 0-7, got {char!r}")
    return int(char)


def _cell(token: str, line: int, col: int) -> Cell:
    if len(token) != 4:
        raise CompileError(line, col, f"a cell is four characters, got {token!r}")
    form = _GLYPHS.get(token[0])
    if form is None:
        raise CompileError(line, col, f"unknown form glyph {token[0]!r}")
    variant = _digit(token[1], line, col + 1, "variant")
    scale = _digit(token[2], line, col + 2, "scale")
    ground = _digit(token[3], line, col + 3, "ground")
    try:
        return Cell(form, variant, scale, ground)
    except ValueError as exc:
        raise CompileError(line, col, str(exc)) from exc


def parse(text: str) -> Plate:
    """Compile .vsr source into a Plate."""
    declared: tuple[int, int] | None = None
    rows: list[tuple[Cell, ...]] = []

    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped == "#" or stripped.startswith("# "):
            continue
        header_match = _HEADER.match(stripped)
        if header_match:
            declared = (int(header_match.group(1)), int(header_match.group(2)))
            continue
        rows.append(
            tuple(
                _cell(match.group(), line_no, match.start() + 1)
                for match in re.finditer(r"\S+", raw)
            )
        )

    if declared is None:
        raise CompileError(1, 1, "missing %plate WxH header")
    if not rows:
        raise CompileError(1, 1, "plate has no cells")

    width = len(rows[0])
    for offset, row in enumerate(rows):
        if len(row) != width:
            raise CompileError(
                1, 1, f"ragged grid: row {offset + 1} has {len(row)} cells, expected {width}"
            )
    height = len(rows)
    if declared != (width, height):
        raise CompileError(
            1,
            1,
            f"header declares {declared[0]}x{declared[1]} but the grid is {width}x{height}",
        )
    return Plate(width, height, tuple(rows))


def _channel(value: int) -> str:
    """Represent a channel value: dot for zero, digit otherwise."""
    return "." if value == 0 else str(value)


def _token(cell: Cell) -> str:
    # A dot means the channel is zero, uniformly in all four positions.
    # This matches the parsing convention that accepts both '.' and '0' to mean zero.
    if cell.is_void:
        return f"...{_channel(cell.ground)}"
    return f"{cell.form.value}{_channel(cell.variant)}{_channel(cell.scale)}{_channel(cell.ground)}"


def emit(plate: Plate) -> str:
    """Render a Plate back to .vsr source."""
    lines = [f"%plate {plate.width}x{plate.height}", ""]
    lines.extend("  ".join(_token(cell) for cell in row) for row in plate.cells)
    return "\n".join(lines) + "\n"
