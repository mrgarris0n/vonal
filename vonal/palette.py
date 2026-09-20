"""The vonal-8 palette. Colours are matched exactly, never approximately."""

PALETTE: tuple[tuple[int, int, int], ...] = (
    (0x11, 0x11, 0x11),
    (0xF2, 0xF0, 0xE9),
    (0x2B, 0x4E, 0xA2),
    (0x4F, 0xA3, 0xD1),
    (0x1E, 0x9B, 0x6B),
    (0xF2, 0xC2, 0x30),
    (0xD6, 0x45, 0x30),
    (0x7B, 0x4B, 0x9B),
)

_BY_RGB = {rgb_value: i for i, rgb_value in enumerate(PALETTE)}


def rgb(index: int) -> tuple[int, int, int]:
    return PALETTE[index]


def index_of(colour: tuple[int, int, int]) -> int | None:
    """Palette index for an exact RGB triple, or None if it is not in the palette."""
    return _BY_RGB.get(colour)
