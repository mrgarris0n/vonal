from vonal import palette, render
from vonal.cell import Cell, Form, Plate


def test_extent_spans_eight_to_fifty_and_always_centres_on_an_integer():
    assert render.extent(0) == 8
    assert render.extent(7) == 50
    for scale in range(8):
        length = render.extent(scale)
        assert length % 2 == 0
        assert (render.CELL - length) % 2 == 0


def test_every_glyph_leaves_ground_visible_at_the_corners():
    # The decoder identifies ground by the corner pixel, so this must always hold.
    for form in (f for f in Form if f is not Form.VOID):
        block = render.template(form, 7)
        assert block[0] == render.GROUND
        assert block[render.CELL - 1] == render.GROUND


def test_template_table_has_eighty_entries_and_excludes_void():
    assert len(render.TEMPLATES) == 80
    assert all(form is not Form.VOID for form, _ in render.TEMPLATES.values())


def test_template_table_is_injective():
    # Construction asserts this; the test pins the guarantee so a future glyph
    # that collides with an existing one fails loudly.
    assert len(set(render.TEMPLATES.values())) == 80


def test_larger_scales_cover_more_pixels():
    for form in (Form.DISC, Form.SQUARE, Form.RHOMBUS, Form.CROSS):
        counts = [sum(render.template(form, s)) for s in range(8)]
        assert counts == sorted(counts)
        assert counts[0] < counts[7]


def test_render_produces_one_64px_block_per_cell():
    plate = Plate(3, 2, tuple(
        tuple(Cell(Form.VOID, ground=1) for _ in range(3)) for _ in range(2)
    ))
    image = render.render(plate)
    assert image.mode == "RGB"
    assert image.size == (192, 128)
    assert image.getpixel((0, 0)) == palette.rgb(1)


def test_render_uses_exactly_two_palette_colours_for_a_non_void_cell():
    plate = Plate(1, 1, ((Cell(Form.DISC, variant=6, scale=4, ground=2),),))
    image = render.render(plate)
    assert {c for _, c in image.getcolors(maxcolors=100)} == {palette.rgb(6), palette.rgb(2)}


def test_render_is_hard_edged():
    # Anti-aliasing would introduce colours outside the palette and break decoding.
    plate = Plate(1, 1, ((Cell(Form.DISC, variant=6, scale=7, ground=2),),))
    for _, colour in render.render(plate).getcolors(maxcolors=100):
        assert palette.index_of(colour) is not None
