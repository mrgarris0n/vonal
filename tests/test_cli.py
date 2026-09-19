from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from vonal import decode, notation, render
from vonal.cli import main
from vonal.errors import LoadError

HELLO = "%plate 3x1\n\no157  +1.7  ....\n"


def test_compile_then_run_the_image(tmp_path, capsys):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    png = tmp_path / "hello.png"

    assert main(["compile", str(src), str(png)]) == 0
    assert png.exists()
    assert main(["run", str(png)]) == 0
    assert capsys.readouterr().out == "5"


def test_run_accepts_source_directly(tmp_path, capsys):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    assert main(["run", str(src)]) == 0
    assert capsys.readouterr().out == "5"


def test_disassemble_round_trips_the_source(tmp_path):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    png = tmp_path / "hello.png"
    back = tmp_path / "back.vsr"

    main(["compile", str(src), str(png)])
    assert main(["disassemble", str(png), str(back)]) == 0
    assert back.read_text() == HELLO


KINETIC = Path(__file__).resolve().parent.parent / "examples" / "kinetic.vsr"


def _gif_durations(path):
    with Image.open(path) as im:
        out = []
        while True:
            out.append(im.info["duration"])
            try:
                im.seek(im.tell() + 1)
            except EOFError:
                return out


def test_trace_to_a_gif_collapses_runs_of_identical_frames(tmp_path):
    gif = tmp_path / "k.gif"
    assert main(["trace", str(KINETIC), str(gif)]) == 0
    # kinetic runs 99 steps but only writes the field 8 times, and writing 0
    # into a cell already at 0 changes no pixels. One frame per distinct image.
    assert len(_gif_durations(gif)) == 8


def test_trace_gif_keeps_the_real_timing_despite_collapsing(tmp_path):
    # Collapsing must not speed the animation up: a stretch where the picture
    # does not change still has to take as long as it did.
    gif = tmp_path / "k.gif"
    main(["trace", str(KINETIC), str(gif), "--frame-ms", "40"])
    frames = tmp_path / "frames"
    main(["trace", str(KINETIC), str(frames)])
    steps = len(list(frames.glob("*.png")))
    assert sum(_gif_durations(gif)) == steps * 40


def test_trace_gif_is_lossless_and_ends_on_the_finished_staircase(tmp_path):
    # GIF is paletted, so the risk is quantisation inventing a colour outside
    # vasarely-8 and making the frames undecodable. Every frame must still be
    # a legal plate, and the last must show the field the program drew.
    gif = tmp_path / "k.gif"
    main(["trace", str(KINETIC), str(gif)])
    with Image.open(gif) as im:
        frames = [f.convert("RGB") for f in ImageSequence.Iterator(im)]
    plates = [decode.decode(f) for f in frames]          # raises if any colour drifted
    assert [plates[-1].at(x, 5).scale for x in range(8)] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert [plates[0].at(x, 5).scale for x in range(8)] == [0] * 8


def test_trace_gif_of_a_plate_that_never_writes_the_field_is_one_frame(tmp_path):
    gif = tmp_path / "c.gif"
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    assert main(["trace", str(src), str(gif)]) == 0
    assert len(_gif_durations(gif)) == 1


def test_compile_refuses_a_lossy_output_format(tmp_path, capsys):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    bad = tmp_path / "hello.jpg"

    assert main(["compile", str(src), str(bad)]) == 1
    assert "lossless" in capsys.readouterr().err
    # Refusing means refusing: no half-written artefact left behind.
    assert not bad.exists()


def test_a_jpeg_of_a_plate_really_is_unloadable(tmp_path):
    # Evidence for the guard above, so it is not taken on faith. Rendering
    # straight to JPEG bypasses the CLI, and the result cannot be decoded:
    # JPEG is lossy and decoding matches palette colours exactly.
    plate = notation.parse(HELLO)
    jpg = tmp_path / "plate.jpg"
    render.render(plate).save(jpg)
    with Image.open(jpg) as image, pytest.raises(LoadError, match="not in the palette"):
        decode.decode(image)


def test_disassemble_without_an_output_path_writes_to_stdout(tmp_path, capsys):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    png = tmp_path / "hello.png"
    main(["compile", str(src), str(png)])

    assert main(["disassemble", str(png)]) == 0

    # Not merely "something was printed": stdout must carry the same canonical
    # source the file form writes, so the two output paths cannot drift, and
    # what lands on stdout must still be a parseable plate.
    printed = capsys.readouterr().out
    assert printed == HELLO
    assert notation.parse(printed) == notation.parse(HELLO)


def test_trace_writes_one_frame_per_step(tmp_path):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    out = tmp_path / "frames"
    assert main(["trace", str(src), str(out)]) == 0
    # A frame before each of push, out and halt.
    assert len(sorted(out.glob("*.png"))) == 3


def test_a_compile_error_exits_nonzero_with_a_message(tmp_path, capsys):
    src = tmp_path / "bad.vsr"
    src.write_text("%plate 1x1\n\no.97\n")
    assert main(["compile", str(src), str(tmp_path / "x.png")]) == 1
    assert "line 3" in capsys.readouterr().err


UNREACHABLE = "%plate 3x2\n\no157  +1.7  ....\no3.7  ....  ....\n"


def test_compile_rejects_an_undefined_opcode_off_the_eyes_path(tmp_path, capsys):
    # DISC variant 3 is undefined. The eye's own path (push 5, print, halt)
    # never reaches (0,1), so the program "looks fine" if only the run were
    # checked -- but the PNG is the canonical program (spec section 6), and a
    # plate that cannot load as an image is not a valid program at all.
    src = tmp_path / "unreachable.vsr"
    src.write_text(UNREACHABLE)
    png = tmp_path / "unreachable.png"

    assert main(["compile", str(src), str(png)]) == 1
    err = capsys.readouterr().err
    assert "vonal:" in err
    assert "(0,1)" in err
    assert "DISC variant 3" in err
    assert not png.exists()


def test_run_on_text_rejects_the_same_undefined_opcode_the_image_would(tmp_path, capsys):
    # Text and image are two representations of one Plate; they must accept
    # the same program set, so `run` on the .vsr source must reject this
    # exactly as loading the compiled PNG would, not merely once the eye
    # happens to step onto the bad cell.
    src = tmp_path / "unreachable.vsr"
    src.write_text(UNREACHABLE)
    assert main(["run", str(src)]) == 1
    assert "vonal:" in capsys.readouterr().err


def test_compile_still_succeeds_for_a_fully_defined_plate(tmp_path):
    src = tmp_path / "hello.vsr"
    src.write_text(HELLO)
    png = tmp_path / "hello.png"
    assert main(["compile", str(src), str(png)]) == 0
    assert png.exists()


def test_max_steps_stops_a_nonterminating_plate(tmp_path):
    src = tmp_path / "loop.vsr"
    src.write_text("%plate 2x1\n\no117  o117\n")
    assert main(["run", str(src), "--max-steps", "10"]) == 0


def test_a_missing_file_exits_nonzero_with_a_message_not_a_traceback(tmp_path, capsys):
    missing = tmp_path / "missing.vsr"
    assert main(["run", str(missing)]) == 1
    assert "vonal:" in capsys.readouterr().err


def test_disassemble_of_a_non_image_exits_nonzero_with_a_message(tmp_path, capsys):
    bogus = tmp_path / "notanimage.png"
    bogus.write_bytes(b"not a png")
    assert main(["disassemble", str(bogus)]) == 1
    assert "vonal:" in capsys.readouterr().err


def test_trace_skips_void_cells_when_field_is_modified(tmp_path):
    # This plate pushes 3, 0, 1 then PUTs to field[1][0] = 3.
    # Cell (0,1) is void, so _with_field must skip it (not construct a void with scale 3).
    src = tmp_path / "put.vsr"
    src.write_text("%plate 5x2\n\no137  o107  o117  @2.7  ....\n....  ....  ....  ....  ....\n")
    out = tmp_path / "frames"
    # Should succeed: trace walks through the execution without error.
    assert main(["trace", str(src), str(out)]) == 0
    # 5 frames: initial, then one after each step (push 3, push 0, push 1, PUT, halt).
    assert len(sorted(out.glob("*.png"))) == 5
