"""compile / disassemble / run / trace."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from vonal import decode, isa, notation, render
from vonal.cell import Cell, Plate
from vonal.errors import VonalError
from vonal.machine import Machine


def _load(path: Path) -> Plate:
    """A .vsr is compiled in memory; anything else is decoded as an image."""
    if path.suffix == ".vsr":
        plate = notation.parse(path.read_text())
        isa.validate(plate)
        return plate
    return decode.load(path)


def _cmd_compile(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.suffix.lower() != ".png":
        # Decoding matches palette colours exactly, so the canonical form has
        # to be lossless. Pillow infers the format from the suffix, and a .jpg
        # would be written happily and then fail to load -- exit 0 now, an
        # unloadable artefact later.
        raise VonalError(
            f"compile writes PNG, but {out.name!r} asks for "
            f"{out.suffix.lower() or 'no extension'}; the canonical form must "
            "be lossless because decoding matches palette colours exactly"
        )
    plate = notation.parse(Path(args.source).read_text())
    isa.validate(plate)
    render.render(plate).save(out)
    return 0


def _cmd_disassemble(args: argparse.Namespace) -> int:
    text = notation.emit(decode.load(args.image))
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def _warn_if_capped(machine: Machine) -> None:
    """Say so when the step cap, not a void cell, is what stopped the machine.

    The two are indistinguishable in the output: a capped `run` prints
    whatever it managed and exits 0, and a capped `trace` writes an animation
    that simply ends. Staying silent leaves a truncated result looking like a
    finished one. Not an error, though -- bounding a plate that never halts is
    what the flag is for -- so this is a note on stderr, not a non-zero exit.
    """
    if not machine.halted:
        print(
            f"vonal: stopped at {machine.steps} steps without halting; "
            "raise --max-steps to go further",
            file=sys.stderr,
        )


def _cmd_run(args: argparse.Namespace) -> int:
    machine = Machine(_load(Path(args.plate)))
    machine.run(max_steps=args.max_steps)
    _warn_if_capped(machine)
    return 0


def _trace_frames(machine: Machine, max_steps: int, every: int = 1) -> Iterator[Image.Image]:
    """The plate as rendered before every `every`-th step, until it halts or hits the cap.

    Only a `put` changes the picture, and it changes one cell, so each frame
    repaints just the cells whose field value moved since the last one rather
    than rendering the whole plate again. A changed frame is a fresh copy and
    an unchanged one is the previous object again, so a consumer may keep any
    frame it is handed without it being drawn over later.

    The state the machine stops in is always a frame, whatever the stride, so
    a sampled trace still ends on the finished picture. When the eye stands on
    a void, the next step halts and cannot change anything, so that is the
    moment to take it.
    """
    plate = machine.plate
    frame = render.render(plate)
    shown = [row[:] for row in machine.field]
    while True:
        final = machine.steps >= max_steps or plate.at(machine.x, machine.y).is_void
        if final or machine.steps % every == 0:
            changed = [
                (x, y, value)
                for y, row in enumerate(machine.field)
                if row != shown[y]
                for x, value in enumerate(row)
                if value != shown[y][x] and not plate.at(x, y).is_void
            ]
            if changed:
                frame = frame.copy()
                for x, y, value in changed:
                    cell = plate.at(x, y)
                    render.paint(frame, x, y, Cell(cell.form, cell.variant, value, cell.ground))
                    shown[y][x] = value
            yield frame
        if machine.steps >= max_steps or not machine.step():
            return


def _save_gif(frames: Iterator[Image.Image], path: Path, frame_ms: int) -> None:
    """Write one animated GIF, collapsing runs of identical frames.

    Most plates never write the field, so most frames are byte-identical to
    their predecessor: a 99-step trace of `kinetic` holds only 8 distinct
    images. Emitting all 99 would bloat the file for no visible gain, so a run
    of identical frames becomes one frame held proportionally longer. The
    animation therefore keeps its real timing -- a stretch where the picture
    does not change still takes as long as it did -- while the file stays the
    size of the change.
    """
    kept: list[Image.Image] = []
    holds: list[int] = []
    for frame in frames:
        # _trace_frames hands back the same object when nothing was repainted.
        if kept and frame is kept[-1]:
            holds[-1] += 1
        else:
            kept.append(frame)
            holds.append(1)

    # A plate uses at most the 8 palette colours, so an adaptive 8-colour
    # palette is exact. Dithering would invent colours the palette does not
    # contain, which is the one thing this format must not do.
    paletted = [
        f.convert("P", dither=Image.Dither.NONE, palette=Image.Palette.ADAPTIVE, colors=8)
        for f in kept
    ]
    paletted[0].save(
        path,
        save_all=True,
        append_images=paletted[1:],
        duration=[h * frame_ms for h in holds],
        loop=0,
    )


def _cmd_trace(args: argparse.Namespace) -> int:
    if args.every < 1:
        raise VonalError(f"--every must be at least 1, got {args.every}")
    machine = Machine(_load(Path(args.plate)))
    out = Path(args.out)
    frames = _trace_frames(machine, args.max_steps, args.every)
    if out.suffix.lower() == ".gif":
        _save_gif(frames, out, args.frame_ms)
    else:
        # A directory keeps one PNG per frame, numbered, for stepping through by
        # hand. No collapsing here: a step that changes nothing is still a step.
        out.mkdir(parents=True, exist_ok=True)
        for n, frame in enumerate(frames):
            frame.save(out / f"{n:05d}.png")
    # After the frames are consumed, so the machine has reached its stopping point.
    _warn_if_capped(machine)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vonal")
    # Read from the installed metadata rather than a second literal here, so
    # pyproject stays the one place the number lives. There is no path where
    # this lookup fails: `vonal` is a console script, so reaching it at all
    # means the distribution is installed.
    parser.add_argument("--version", action="version", version=f"vonal {version('vonal')}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("compile", help="compile .vsr source to a plate image")
    p.add_argument("source")
    p.add_argument("out")
    p.set_defaults(func=_cmd_compile)

    p = sub.add_parser("disassemble", help="read a plate image back as .vsr")
    p.add_argument("image")
    p.add_argument("out", nargs="?")
    p.set_defaults(func=_cmd_disassemble)

    p = sub.add_parser("run", help="execute a plate (.vsr or .png)")
    p.add_argument("plate")
    p.add_argument("--max-steps", type=int, default=None)
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser(
        "trace",
        help="write one frame per step (or per --every N): a directory of PNGs, or an animated .gif",
    )
    p.add_argument("plate")
    p.add_argument("out", help="a directory, or a path ending .gif to animate")
    p.add_argument("--max-steps", type=int, default=1000)
    p.add_argument(
        "--every", type=int, default=1, help="keep one frame every N steps, plus the last"
    )
    p.add_argument(
        "--frame-ms", type=int, default=100, help="milliseconds per frame in a .gif"
    )
    p.set_defaults(func=_cmd_trace)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except VonalError as exc:
        print(f"vonal: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnidentifiedImageError) as exc:
        # A missing/unreadable file, or an image Pillow cannot identify --
        # not a Vonal-level fault, but still not a traceback the user should
        # see. Anything else genuinely unexpected keeps propagating.
        print(f"vonal: {exc}", file=sys.stderr)
        return 1
