import io
from pathlib import Path

from vonal import decode, notation, render
from vonal.machine import Machine

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def output_of(name, max_steps=200_000):
    plate = notation.parse((EXAMPLES / name).read_text())
    out = io.StringIO()
    machine = Machine(plate, stdin=io.StringIO(""), stdout=out)
    machine.run(max_steps=max_steps)
    assert machine.halted, f"{name} did not halt within {max_steps} steps"
    return out.getvalue()


def round_trips(name):
    plate = notation.parse((EXAMPLES / name).read_text())
    return decode.decode(render.render(plate)) == plate


def test_countdown_counts_down_from_five():
    assert output_of("countdown.vsr") == "54321"


def test_countdown_survives_a_full_image_round_trip():
    assert round_trips("countdown.vsr")


def test_fibonacci_prints_the_first_ten_terms():
    assert output_of("fibonacci.vsr") == "1 1 2 3 5 8 13 21 34 55 "


def test_collatz_prints_the_trajectory_of_six():
    assert output_of("collatz.vsr") == "6 3 10 5 16 8 4 2 1 "


def test_fibonacci_survives_a_full_image_round_trip():
    assert round_trips("fibonacci.vsr")


def test_collatz_survives_a_full_image_round_trip():
    assert round_trips("collatz.vsr")
