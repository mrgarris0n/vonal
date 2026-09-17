import io
from pathlib import Path

from PIL import Image

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
    # Checks two things, not one: that in-memory render/decode is a genuine
    # inverse (as the round-trip property tests already cover generally),
    # and -- what nothing else in this suite opens -- that the *shipped*
    # examples/*.png on disk still decodes to the same plate as the current
    # .vsr source. Without the second half, editing the source and forgetting
    # to `vonal compile` leaves a stale PNG that nothing catches.
    plate = notation.parse((EXAMPLES / name).read_text())
    if decode.decode(render.render(plate)) != plate:
        return False
    png_path = (EXAMPLES / name).with_suffix(".png")
    return decode.decode(Image.open(png_path)) == plate


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
