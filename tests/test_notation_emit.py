from hypothesis import given, settings

from vonal.cell import Cell, Form, Plate
from vonal.notation import emit, parse
from tests.strategies import plates


def test_emit_writes_the_header_and_aligned_tokens():
    plate = Plate(2, 1, ((Cell(Form.DISC, 0, 5, 1), Cell(Form.VOID)),))
    text = emit(plate)
    assert text.splitlines()[0] == "%plate 2x1"
    assert "o051  ...0" in text


def test_emit_writes_a_void_ground_but_dots_for_its_dead_channels():
    plate = Plate(1, 1, ((Cell(Form.VOID, 0, 0, 4),),))
    assert "...4" in emit(plate)


@given(plates())
@settings(max_examples=200)
def test_text_round_trip_is_identity(plate):
    assert parse(emit(plate)) == plate
