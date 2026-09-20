import hashlib
import io
import random
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from vonal import cli, decode, isa, notation, render
from vonal.cell import Cell, Form, Plate
from vonal.machine import Machine

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def output_of_plate(plate, max_steps=200_000, label="plate", stdin=""):
    out = io.StringIO()
    machine = Machine(plate, stdin=io.StringIO(stdin), stdout=out)
    machine.run(max_steps=max_steps)
    assert machine.halted, f"{label} did not halt within {max_steps} steps"
    return out.getvalue()


def output_of(name, max_steps=200_000, stdin=""):
    plate = notation.parse((EXAMPLES / name).read_text())
    return output_of_plate(plate, max_steps, name, stdin)


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
    with Image.open(png_path) as image:
        return decode.decode(image) == plate


def test_countdown_counts_down_from_five():
    assert output_of("countdown.vsr") == "54321\n"


def test_countdown_survives_a_full_image_round_trip():
    assert round_trips("countdown.vsr")


def test_fibonacci_prints_the_first_ten_terms():
    assert output_of("fibonacci.vsr") == "1 1 2 3 5 8 13 21 34 55 \n"


def test_collatz_prints_the_trajectory_of_six():
    assert output_of("collatz.vsr") == "6 3 10 5 16 8 4 2 1 \n"


def test_fibonacci_survives_a_full_image_round_trip():
    assert round_trips("fibonacci.vsr")


def test_collatz_survives_a_full_image_round_trip():
    assert round_trips("collatz.vsr")


def test_orb_prints_five():
    assert output_of("orb.vsr") == "5\n"


def test_orb_survives_a_full_image_round_trip():
    assert round_trips("orb.vsr")


def test_hello_prints_hello_world():
    assert output_of("hello.vsr") == "Hello, World!\n"


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


def test_collatz_in_given_six_matches_the_hardcoded_collatz():
    # The two plates differ by exactly one cell, so feeding the literal that
    # the other one bakes in must reproduce it byte for byte.
    assert output_of("collatz-in.vsr", stdin="6\n") == output_of("collatz.vsr")


def test_collatz_in_follows_an_arbitrary_seed():
    # 27 is the standard demonstration: 112 terms, peaking at 9232 before it
    # collapses. Matching those two numbers is what shows the plate computes
    # from input rather than from anything written into its own picture.
    terms = output_of("collatz-in.vsr", stdin="27\n").split()
    assert len(terms) == 112
    assert max(int(t) for t in terms) == 9232
    assert terms[0] == "27" and terms[-1] == "1"


def test_collatz_in_halts_immediately_on_one():
    assert output_of("collatz-in.vsr", stdin="1\n") == "1 \n"


def test_collatz_in_survives_a_full_image_round_trip():
    assert round_trips("collatz-in.vsr")


@pytest.mark.parametrize(
    "n,expected",
    [
        (-3, "0"), (0, "0"), (1, "0"),   # turned away by the LT guard before the loop
        (2, "1"),                        # composite if divisibility is tested first
        (3, "1"), (4, "0"), (9, "0"), (25, "0"),
        (29, "1"), (97, "1"), (100, "0"), (101, "1"),
    ],
)
def test_prime_decides_correctly(n, expected):
    assert output_of("prime.vsr", stdin=f"{n}\n") == expected + "\n"


def test_prime_survives_a_full_image_round_trip():
    assert round_trips("prime.vsr")


def test_the_shipped_kinetic_gif_is_not_stale(tmp_path):
    # examples/kinetic.gif is committed so the animation is visible without
    # running anything, which means it can drift from the plate exactly as the
    # PNGs could. Regenerate and compare what matters: the number of distinct
    # frames, and the field the last one shows.
    fresh = tmp_path / "fresh.gif"
    assert cli.main(["trace", str(EXAMPLES / "kinetic.vsr"), str(fresh)]) == 0

    def summary(path):
        with Image.open(path) as im:
            frames = [f.convert("RGB") for f in ImageSequence.Iterator(im)]
        last = decode.decode(frames[-1])
        return len(frames), [last.at(x, 5).scale for x in range(8)]

    assert summary(EXAMPLES / "kinetic.gif") == summary(fresh)
    assert summary(fresh) == (8, [0, 1, 2, 3, 4, 5, 6, 7])


@pytest.mark.parametrize(
    "chars,largest",
    [
        ("abc", 99), ("acb", 99), ("bac", 99),
        ("bca", 99), ("cab", 99), ("cba", 99),   # every ordering: both detours fire
        ("aaa", 97), ("aab", 98), ("aba", 98), ("baa", 98),   # ties
        ("Az0", 122), ("!~ ", 126),
    ],
)
def test_span_prints_the_largest_and_its_negation(chars, largest):
    assert output_of("span.vsr", stdin=chars) == f"{largest} {-largest}\n"


def test_span_survives_a_full_image_round_trip():
    assert round_trips("span.vsr")


MIRROR_PROFILE = "1 2 3 4 5 5 6 7 6 5 5 4 3 2 1 "


def test_mirror_prints_the_profile_of_its_own_swell():
    assert output_of("mirror.vsr") == MIRROR_PROFILE + "\n"


def test_mirror_survives_a_full_image_round_trip():
    assert round_trips("mirror.vsr")


def test_mirror_reads_the_picture_rather_than_reciting_it():
    # The claim this plate exists to make is that GET turns composition into
    # data, so the output must be derived from the field and not spelled out
    # somewhere in the program. Perturb one cell of the row being read: only
    # that position of the output may move. A recited literal could not.
    plate = notation.parse((EXAMPLES / "mirror.vsr").read_text())
    before = output_of_plate(plate).split()
    assert before[0] == "1"

    original = plate.at(0, 7)
    assert original.scale == 1
    perturbed = plate.replaced(
        0, 7, Cell(original.form, original.variant, 7, original.ground)
    )
    after = output_of_plate(perturbed).split()

    assert after[0] == "7", "the first column's scale was not read from the plate"
    assert after[1:] == before[1:], "perturbing one cell disturbed other columns"


def test_orb_is_a_swell_and_not_a_flat_field():
    # This plate exists to demonstrate that scale is a free compositional
    # channel, so the gradient *is* the deliverable. A regeneration that
    # flattened it would still print "5" and still round-trip, and the two
    # tests above would both pass -- only this one would notice.
    plate = notation.parse((EXAMPLES / "orb.vsr").read_text())
    scales = {
        plate.at(x, y).scale
        for y in range(plate.height)
        for x in range(plate.width)
    }
    assert len(scales) >= 7, f"gradient collapsed to {sorted(scales)}"

    centre = plate.at(plate.width // 2, plate.height // 2).scale
    corner = plate.at(plate.width - 1, plate.height - 1).scale
    assert centre > corner, f"centre {centre} should swell above corner {corner}"


BUBBLE_START = [5, 3, 7, 1, 6, 0, 4, 2]


def test_bubble_prints_the_sorted_row():
    assert output_of("bubble.vsr") == "0 1 2 3 4 5 6 7 \n"


def test_bubble_survives_a_full_image_round_trip():
    assert round_trips("bubble.vsr")


def test_bubble_sorts_its_own_picture_in_place():
    # The printed line is only half the output. The other half is the plate:
    # row 7 starts scrambled and ends as a rising staircase, which is what
    # `vonal trace` animates. As with kinetic, the field is a copy, so the
    # plate itself must come through untouched.
    plate = notation.parse((EXAMPLES / "bubble.vsr").read_text())
    assert [plate.at(x, 7).scale for x in range(8)] == BUBBLE_START

    machine = Machine(plate, stdin=io.StringIO(""), stdout=io.StringIO())
    machine.run(max_steps=50_000)
    assert machine.halted
    assert machine.field[7][:8] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert [plate.at(x, 7).scale for x in range(8)] == BUBBLE_START


@pytest.mark.parametrize(
    "values",
    [
        [0, 1, 2, 3, 4, 5, 6, 7],   # already sorted: 49 iterations, no swaps
        [7, 6, 5, 4, 3, 2, 1, 0],   # reversed: the worst case
        [3, 3, 3, 3, 3, 3, 3, 3],   # all equal: GT must not swap on a tie
        [7, 7, 7, 7, 0, 0, 0, 0],   # every element has to travel the full width
        [1, 0, 1, 0, 1, 0, 1, 0],   # duplicates interleaved
        [2, 5, 5, 1, 0, 7, 7, 3],
    ],
)
def test_bubble_sorts_whatever_is_in_its_data_row(values):
    # The claim is that this sorts, not that it recites one answer. Reseeding
    # row 7 is the only way to tell the two apart: a plate that merely printed
    # 0..7 would pass the test above and fail every case here.
    plate = notation.parse((EXAMPLES / "bubble.vsr").read_text())
    for x, value in enumerate(values):
        cell = plate.at(x, 7)
        plate = plate.replaced(x, 7, Cell(cell.form, cell.variant, value, cell.ground))

    out = io.StringIO()
    machine = Machine(plate, stdin=io.StringIO(""), stdout=out)
    machine.run(max_steps=50_000)

    assert machine.halted
    assert machine.field[7][:8] == sorted(values)
    assert out.getvalue() == " ".join(str(v) for v in sorted(values)) + " \n"


def test_the_shipped_bubble_gif_is_not_stale(tmp_path):
    # Committed so the sort is visible without running anything, and therefore
    # able to drift from the plate exactly as the PNGs could. Note the step
    # cap: this plate runs 1801 steps, so the trace default of 1000 would stop
    # it mid-sort and the last frame would not be sorted at all.
    fresh = tmp_path / "fresh.gif"
    assert cli.main(
        ["trace", str(EXAMPLES / "bubble.vsr"), str(fresh), "--max-steps", "2000"]
    ) == 0

    def summary(path):
        with Image.open(path) as im:
            frames = [f.convert("RGB") for f in ImageSequence.Iterator(im)]
        return (
            len(frames),
            [decode.decode(frames[0]).at(x, 7).scale for x in range(8)],
            [decode.decode(frames[-1]).at(x, 7).scale for x in range(8)],
        )

    assert summary(EXAMPLES / "bubble.gif") == summary(fresh)
    assert summary(fresh) == (37, BUBBLE_START, [0, 1, 2, 3, 4, 5, 6, 7])


SWELL_TOP = 5  # the first composition row; rows 0-4 are the program
SWELL_FLAT = 3  # the one size every square ships at


def swell_falloff(x, y):
    """The radial falloff swell.vsr computes, in region coordinates."""
    return 7 - ((x - 7) ** 2 + (y - 7) ** 2) // 14


def swell_expected():
    return [[swell_falloff(x, y) for x in range(15)] for y in range(15)]


def swell_field(plate):
    return [[plate.at(x, y + SWELL_TOP).scale for x in range(15)] for y in range(15)]


def test_the_swell_falloff_uses_the_whole_range_and_no_more():
    # Why the loop body needs no clamp, and so no branch: PUT rejects anything
    # outside 0-7 as a runtime fault, and the corner is 7*7 + 7*7 = 98 with
    # 98 // 14 == 7 exactly, so the falloff reaches both ends and neither past.
    values = [v for row in swell_expected() for v in row]
    assert (min(values), max(values)) == (0, 7)


def test_swell_ships_flat_and_computes_its_own_bulge():
    plate = notation.parse((EXAMPLES / "swell.vsr").read_text())
    # The claim is that the picture is computed, not authored. A plate that
    # shipped with the swell already in its scales would pass every other
    # assertion here while demonstrating nothing.
    assert set(v for row in swell_field(plate) for v in row) == {SWELL_FLAT}

    machine = Machine(plate, stdin=io.StringIO(""), stdout=io.StringIO())
    machine.run(max_steps=20_000)

    assert machine.halted
    assert [machine.field[y + SWELL_TOP] for y in range(15)] == swell_expected()
    # The field is a copy, as with kinetic and bubble: the plate is immutable.
    assert set(v for row in swell_field(plate) for v in row) == {SWELL_FLAT}


def test_swell_survives_a_full_image_round_trip():
    assert round_trips("swell.vsr")


def test_the_shipped_swell_gif_is_not_stale():
    # Not re-traced the way bubble's is. This plate runs 13,516 steps and
    # `trace` renders one frame per step, so regenerating it here would cost
    # minutes for a plate that changes 201 times. The two frames that carry
    # the claim are enough: a GIF of some older plate fails on the last one.
    with Image.open(EXAMPLES / "swell.gif") as image:
        frames = [frame.convert("RGB") for frame in ImageSequence.Iterator(image)]

    # 202, not 226: 24 of the 225 cells compute to the size they already
    # shipped at, and a write that changes no pixel is collapsed away.
    assert len(frames) == 202
    assert set(v for row in swell_field(decode.decode(frames[0])) for v in row) == {SWELL_FLAT}
    assert swell_field(decode.decode(frames[-1])) == swell_expected()


@pytest.mark.parametrize(
    "name,stdin",
    [("countdown.vsr", ""), ("hello.vsr", ""), ("mirror.vsr", ""),
     ("bubble.vsr", ""), ("prime.vsr", "97\n"), ("span.vsr", "abc")],
)
def test_a_plate_can_be_recoloured_without_changing_what_it_does(name, stdin):
    # The property the relative encoding exists for, and the reason the
    # variant is an offset rather than a colour. Rotating a cell's ground
    # carries its figure along, so the instruction is untouched. Every cell
    # gets an independent random ground here, which under the old absolute
    # encoding would have been illegal wherever the ground met the figure
    # colour, and would have changed the opcode everywhere else.
    base = notation.parse((EXAMPLES / name).read_text())
    expected = output_of_plate(base, label=name, stdin=stdin)

    rng = random.Random(1906)
    recoloured = Plate(base.width, base.height, tuple(
        tuple(
            cell if cell.is_void
            else Cell(cell.form, cell.variant, cell.scale, rng.randrange(8))
            for cell in row
        )
        for row in base.cells
    ))

    isa.validate(recoloured)
    assert output_of_plate(recoloured, label=name, stdin=stdin) == expected
    assert decode.decode(render.render(recoloured)) == recoloured

    grounds = {c.ground for row in recoloured.cells for c in row}
    figures = {c.figure for row in recoloured.cells for c in row if not c.is_void}
    assert len(grounds) == 8, "the recolouring did not exercise every ground"
    assert len(figures) == 8, f"only {len(figures)} figure colours reachable"


def _scale_total(plate):
    return sum(cell.scale for row in plate.cells for cell in row)


def test_tally_prints_its_own_weight():
    plate = notation.parse((EXAMPLES / "tally.vsr").read_text())
    # Not a hardcoded 613: the number has to be the sum the plate actually
    # carries, so regenerating the composition cannot leave the two disagreeing.
    assert output_of("tally.vsr") == f"{_scale_total(plate)}\n"


def test_tally_survives_a_full_image_round_trip():
    assert round_trips("tally.vsr")


@pytest.mark.parametrize("x,y", [(6, 13), (3, 9), (11, 7), (23, 15), (1, 3)])
def test_tally_weighs_the_picture_rather_than_reciting_a_number(x, y):
    # The claim is that it reads all 384 cells, its own loop included, so
    # resizing any one of them must move the total by exactly that much.
    # (1,3) is an instruction in the loop body, which is the interesting case:
    # the program counts itself.
    plate = notation.parse((EXAMPLES / "tally.vsr").read_text())
    before = int(output_of_plate(plate, label="tally"))
    assert before == _scale_total(plate)

    cell = plate.at(x, y)
    assert not cell.is_void
    changed = (cell.scale + 3) % 8
    perturbed = plate.replaced(x, y, Cell(cell.form, cell.variant, changed, cell.ground))

    after = int(output_of_plate(perturbed, label="tally"))
    assert after == before - cell.scale + changed


def test_tally_uses_every_colour_as_both_ground_and_figure():
    # The reason this plate exists. Under the old absolute encoding it was
    # impossible: the variant was the figure colour, so only the six colours
    # some opcode used could be drawn, and every push disc was black.
    plate = notation.parse((EXAMPLES / "tally.vsr").read_text())
    grounds = {c.ground for row in plate.cells for c in row}
    figures = {c.figure for row in plate.cells for c in row if not c.is_void}
    assert grounds == set(range(8)), f"grounds {sorted(grounds)}"
    assert figures == set(range(8)), f"figures {sorted(figures)}"


def test_orb_no_longer_needs_a_ground_that_advertises_its_code():
    # This plate used to carry a yellow strip over cells (2,0) to (4,0), and
    # not for compositional reasons: under the absolute encoding those cells'
    # variant matched the cream ground, which was forbidden, so they were
    # forced onto a different one. With variants as offsets the collision
    # cannot arise, so the program sits on the same ground as its neighbours.
    plate = notation.parse((EXAMPLES / "orb.vsr").read_text())
    field = plate.at(8, 0).ground                     # the outer band
    assert [plate.at(x, 0).ground for x in range(6)] == [field] * 6

    # And the rekeyed ground gives the figures somewhere to go.
    figures = {c.figure for row in plate.cells for c in row if not c.is_void}
    assert len(figures) > 1, "the swell is still monochrome"


QUINE = EXAMPLES / "quine.vsr"


def test_quine_prints_its_own_source_exactly():
    # The whole claim, and it has to be byte equality against the file on
    # disk, not against a regenerated plate: quine.vsr therefore carries no
    # comment header, because a comment is not part of the canonical form and
    # the plate could never reproduce it.
    source = QUINE.read_text()
    assert output_of("quine.vsr", max_steps=1_000_000) == source


def test_the_quine_image_prints_the_same_source():
    # The PNG is the canonical program, so the claim has to survive the round
    # trip through pixels, not just hold for the text form.
    with Image.open(EXAMPLES / "quine.png") as image:
        plate = decode.decode(image)
    printed = output_of_plate(plate, max_steps=1_000_000, label="quine.png")
    assert printed == QUINE.read_text()


def test_the_quine_is_a_fixed_point_of_the_whole_toolchain():
    # Stronger than printing itself: what it prints must compile to the same
    # image, so output -> compile -> decode -> run is a closed loop.
    plate = notation.parse(QUINE.read_text())
    printed = output_of_plate(plate, max_steps=1_000_000, label="quine")
    assert notation.parse(printed) == plate
    assert decode.decode(render.render(notation.parse(printed))) == plate


def test_the_quine_reads_its_own_data_rather_than_reciting_it():
    # A plate that merely spelled out 33326 characters would pass every test
    # above. Resize one padding disc past the encoded region: the output must
    # move in exactly one place, the token for that cell, and must still be a
    # true description of the plate it now is.
    plate = notation.parse(QUINE.read_text())
    x, y = 40, 95
    cell = plate.at(x, y)
    assert cell.form is Form.DISC and cell.scale != 0

    changed = 1 + (cell.scale % 7)
    perturbed = plate.replaced(x, y, Cell(cell.form, cell.variant, changed, cell.ground))
    printed = output_of_plate(perturbed, max_steps=1_000_000, label="quine perturbed")

    assert printed == notation.emit(perturbed), "it stopped describing itself"
    moved = [i for i, (a, b) in enumerate(zip(notation.emit(plate), printed)) if a != b]
    assert len(moved) == 1, f"{len(moved)} characters moved, expected 1"


def test_a_cell_inside_the_encoded_region_is_load_bearing_twice():
    # The other half of the same point, and the reason the cell above had to
    # be chosen past row 95. Rows 5 onward are printed from their own scales
    # AND read as the base-7 digits spelling out rows 0 to 4. A cell in that
    # overlap is read twice, so changing it breaks the description: the token
    # printed for the cell moves, and so does a character of the program text
    # it helps encode. Self-reference here is not free.
    plate = notation.parse(QUINE.read_text())
    cell = plate.at(40, 90)
    perturbed = plate.replaced(
        40, 90, Cell(cell.form, cell.variant, 1 + (cell.scale % 7), cell.ground)
    )
    printed = output_of_plate(perturbed, max_steps=1_000_000, label="quine data")

    assert printed != notation.emit(perturbed)
    moved = [i for i, (a, b) in enumerate(zip(notation.emit(plate), printed)) if a != b]
    assert len(moved) > 1, "a data cell should disturb more than its own token"
