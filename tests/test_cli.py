from vonal import notation
from vonal.cli import main

HELLO = "%plate 3x1\n\no.57  +..7  ....\n"


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


UNREACHABLE = "%plate 3x2\n\no.57  +..7  ....\no2.7  ....  ....\n"


def test_compile_rejects_an_undefined_opcode_off_the_eyes_path(tmp_path, capsys):
    # DISC variant 2 is undefined. The eye's own path (push 5, print, halt)
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
    assert "DISC variant 2" in err
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
    src.write_text("%plate 2x1\n\no.17  o.17\n")
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
    src.write_text("%plate 5x2\n\no.37  o.07  o.17  @1.7  ....\n....  ....  ....  ....  ....\n")
    out = tmp_path / "frames"
    # Should succeed: trace walks through the execution without error.
    assert main(["trace", str(src), str(out)]) == 0
    # 5 frames: initial, then one after each step (push 3, push 0, push 1, PUT, halt).
    assert len(sorted(out.glob("*.png"))) == 5
