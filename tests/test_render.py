from vonal import palette, render
from vonal.cell import Cell, Form, Plate


def test_extent_spans_eight_to_fifty_and_always_centres_on_an_integer():
    assert render.extent(0) == 8
    assert render.extent(7) == 50
    for scale in range(8):
        length = render.extent(scale)
        assert length % 2 == 0
        assert (render.CELL - length) % 2 == 0


def test_every_glyph_leaves_ground_visible_at_all_four_corners_at_every_scale():
    # The decoder identifies ground by the corner pixel (0,0), so this must
    # hold everywhere it's relied on. The previous version of this test
    # checked byte 0 (top-left) and byte CELL-1 -- which is the *top-right*
    # corner of a row-major CELL*CELL buffer, not bottom-right -- so both
    # bottom corners went unchecked, and only the largest scale was tried.
    top_left, top_right = 0, render.CELL - 1
    bottom_left = (render.CELL - 1) * render.CELL
    bottom_right = render.CELL * render.CELL - 1
    corners = (top_left, top_right, bottom_left, bottom_right)
    for form in (f for f in Form if f is not Form.VOID):
        for scale in range(8):
            block = render.template(form, scale)
            for corner in corners:
                assert block[corner] == render.GROUND


def test_every_template_contains_both_a_form_and_a_ground_pixel():
    # This is what stops a glyph decoding as void: decode() treats a cell
    # showing a single colour as void (decode.py), so a template that never
    # draws any FORM pixel at all -- or is FORM everywhere, leaving no
    # ground -- would be indistinguishable from void, or fail to decode.
    for mask in render.TEMPLATES:
        assert render.FORM in mask
        assert render.GROUND in mask


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
