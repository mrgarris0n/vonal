import hashlib
import io
from pathlib import Path

from PIL import Image

from vonal import cli, decode, notation, render
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


def test_vega_prints_five():
    assert output_of("vega.vsr") == "5"


def test_vega_survives_a_full_image_round_trip():
    assert round_trips("vega.vsr")


def test_hello_prints_hello_world():
    assert output_of("hello.vsr") == "Hello, World!"


def test_hello_survives_a_full_image_round_trip():
    assert round_trips("hello.vsr")


def test_kinetic_prints_nothing_and_halts():
    # output_of asserts the machine halted, which is the whole assertion here:
    # this plate's output is the plate, not stdout.
    assert output_of("kinetic.vsr") == ""


def test_kinetic_survives_a_full_image_round_trip():
    assert round_trips("kinetic.vsr")


def test_kinetic_draws_a_staircase_into_its_own_field():
    plate = notation.parse((EXAMPLES / "kinetic.vsr").read_text())
    machine = Machine(plate, stdin=io.StringIO(""), stdout=io.StringIO())
    machine.run(max_steps=2000)
    assert machine.halted
    assert machine.field[5][:8] == [0, 1, 2, 3, 4, 5, 6, 7]
    # The field is a copy; the plate itself must be untouched.
    assert [plate.at(x, 5).scale for x in range(8)] == [0] * 8


def test_kinetic_trace_frames_actually_differ(tmp_path):
    # The point of this plate, and the only test in the suite that pins it: a
    # running program deforms its own picture. Every other example traces to
    # byte-identical frames because none of them writes the field, so a
    # regression in the trace rebuild would be invisible without this.
    assert cli.main(["trace", str(EXAMPLES / "kinetic.vsr"), str(tmp_path)]) == 0
    frames = sorted(tmp_path.glob("*.png"))
    digests = {hashlib.sha256(f.read_bytes()).hexdigest() for f in frames}
    assert len(frames) > 1
    assert len(digests) == 8, f"expected 8 distinct frames, got {len(digests)}"


def test_vega_is_a_swell_and_not_a_flat_field():
    # This plate exists to demonstrate that scale is a free compositional
    # channel, so the gradient *is* the deliverable. A regeneration that
    # flattened it would still print "5" and still round-trip, and the two
    # tests above would both pass -- only this one would notice.
    plate = notation.parse((EXAMPLES / "vega.vsr").read_text())
    scales = {
        plate.at(x, y).scale
        for y in range(plate.height)
        for x in range(plate.width)
    }
    assert len(scales) >= 7, f"gradient collapsed to {sorted(scales)}"

    centre = plate.at(plate.width // 2, plate.height // 2).scale
    corner = plate.at(plate.width - 1, plate.height - 1).scale
    assert centre > corner, f"centre {centre} should swell above corner {corner}"
