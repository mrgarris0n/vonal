import pytest
from vonal.cell import Form
from vonal.errors import CompileError
from vonal.notation import parse

HELLO = """%plate 5x2

o.57  +0.7  ....  ....  ....
....  ....  ....  ....  ....
"""


def test_parses_the_worked_example():
    plate = parse(HELLO)
    assert (plate.width, plate.height) == (5, 2)
    push = plate.at(0, 0)
    assert (push.form, push.variant, push.scale, push.ground) == (Form.DISC, 0, 5, 7)
    out = plate.at(1, 0)
    assert (out.form, out.variant, out.ground) == (Form.CROSS, 0, 7)
    assert plate.at(2, 0).is_void


def test_dot_means_zero_outside_the_form_position():
    plate = parse("%plate 1x1\n\n@1.3\n")
    cell = plate.at(0, 0)
    assert (cell.form, cell.variant, cell.scale, cell.ground) == (Form.RING, 1, 0, 3)


def test_comments_and_blank_lines_are_ignored():
    plate = parse("# a note\n%plate 1x1\n\n\n....\n\n")
    assert plate.at(0, 0).is_void


def test_plate_header_mismatch_is_a_compile_error():
    with pytest.raises(CompileError, match="declares 3x1"):
        parse("%plate 3x1\n\no.17  ....\n")


def test_ragged_rows_are_a_compile_error():
    with pytest.raises(CompileError, match="ragged"):
        parse("%plate 2x2\n\no.17  ....\n....\n")


def test_unknown_form_glyph_is_a_compile_error():
    with pytest.raises(CompileError, match="unknown form"):
        parse("%plate 1x1\n\nZ...\n")


def test_token_of_wrong_length_is_a_compile_error():
    with pytest.raises(CompileError, match="four characters"):
        parse("%plate 1x1\n\no.1\n")


def test_digit_out_of_range_is_a_compile_error():
    with pytest.raises(CompileError, match="0-7"):
        parse("%plate 1x1\n\no.97\n")


def test_cell_validity_errors_carry_the_token_position():
    # o5.5: form colour 5 equals ground 5, so the glyph would be invisible.
    with pytest.raises(CompileError) as excinfo:
        parse("%plate 2x1\n\n....  o5.5\n")
    assert excinfo.value.line == 3
    assert excinfo.value.col == 7
    assert "ground" in str(excinfo.value)


@pytest.mark.parametrize("token", ["..3.", ".3.."])
def test_void_with_a_nonzero_channel_is_a_compile_error(token):
    with pytest.raises(CompileError, match="void"):
        parse(f"%plate 1x1\n\n{token}\n")


def test_missing_header_is_a_compile_error():
    with pytest.raises(CompileError, match="%plate"):
        parse("o.17\n")


def test_square_glyph_can_start_a_row():
    # SQUARE form glyph '#' can start a row and should not be treated as a comment.
    plate = parse("%plate 1x1\n\n#075\n")
    cell = plate.at(0, 0)
    assert cell.form is Form.SQUARE
    assert (cell.variant, cell.scale, cell.ground) == (0, 7, 5)


def test_rhombus_glyph_can_start_a_row():
    # RHOMBUS form glyph '%' can start a row and should not be treated as a directive.
    plate = parse("%plate 1x1\n\n%142\n")
    cell = plate.at(0, 0)
    assert cell.form is Form.RHOMBUS
    assert (cell.variant, cell.scale, cell.ground) == (1, 4, 2)


def test_comment_line_with_hash_space_is_ignored():
    # A line starting with '# ' (hash-space) is a comment.
    plate = parse("%plate 1x1\n\n# this is a comment\n#075\n")
    cell = plate.at(0, 0)
    assert cell.form is Form.SQUARE
    assert (cell.variant, cell.scale, cell.ground) == (0, 7, 5)


def test_bare_hash_is_a_comment():
    # A line containing only '#' is a comment.
    plate = parse("%plate 1x1\n\n#\n#075\n")
    cell = plate.at(0, 0)
    assert cell.form is Form.SQUARE
    assert (cell.variant, cell.scale, cell.ground) == (0, 7, 5)
