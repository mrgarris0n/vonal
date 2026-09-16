from vonal import palette


def test_palette_has_eight_exact_colours():
    assert len(palette.PALETTE) == 8
    assert palette.PALETTE[0] == (0x11, 0x11, 0x11)
    assert palette.PALETTE[5] == (0xF2, 0xC2, 0x30)


def test_rgb_and_index_of_are_inverses():
    for i in range(8):
        assert palette.index_of(palette.rgb(i)) == i


def test_index_of_returns_none_for_unknown_colour():
    assert palette.index_of((1, 2, 3)) is None
