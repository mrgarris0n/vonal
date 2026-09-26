"""compile / disassemble / run / trace."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterator
from importlib.metadata import version
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from vonal import decode, isa, notation, palette, render
from vonal.cell import Cell, Plate
from vonal.errors import VonalError
from vonal.machine import Machine


def _positive_int(text: str) -> int:
    """An argparse type for counts where zero or less would do nothing useful.

    A cap of 0 or below stops the machine before its first step, and the only
    sign is the capped-run note, which then blames the cap rather than the
    argument. Rejected at parse time instead, with the usage line.
    """
    try:
        value = int(text)
    except ValueError:
        # Otherwise argparse names this function in the message.
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


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


def _trace_frames(
    machine: Machine, max_steps: int, every: int = 1, eye: bool = False
) -> Iterator[Image.Image]:
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

    With `eye`, each frame also outlines the cell the eye is about to run. The
    outline goes on a copy, so the unmarked frame stays the base for repaints.
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
            if eye:
                marked = frame.copy()
                render.mark(marked, machine.x, machine.y)
                yield marked
            else:
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

    # A frame is drawn in the vonal palette and nothing else, so mapping it
    # onto that palette is exact. Dithering would invent colours the palette
    # does not contain, which is the one thing this format must not do.
    #
    # One fixed palette for every frame, and optimize=False so Pillow keeps it
    # rather than trimming each frame to the colours it uses. Either an
    # adaptive palette per frame or the trimming leaves frames with differing
    # palettes, which the GIF writer then remaps pixel by pixel onto a common
    # one; between them that was nearly all of a trace's time.
    vonal_palette = Image.new("P", (1, 1))
    vonal_palette.putpalette([channel for rgb in palette.PALETTE for channel in rgb])
    paletted = [f.quantize(palette=vonal_palette, dither=Image.Dither.NONE) for f in kept]
    paletted[0].save(
        path,
        save_all=True,
        append_images=paletted[1:],
        duration=[h * frame_ms for h in holds],
        loop=0,
        optimize=False,
    )


def _cmd_trace(args: argparse.Namespace) -> int:
    machine = Machine(_load(Path(args.plate)))
    out = Path(args.out)
    frames = _trace_frames(machine, args.max_steps, args.every, args.eye)
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
    p.add_argument("--max-steps", type=_positive_int, default=None)
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser(
        "trace",
        help="write one frame per step (or per --every N): "
        "a directory of PNGs, or an animated .gif",
    )
    p.add_argument("plate")
    p.add_argument("out", help="a directory, or a path ending .gif to animate")
    p.add_argument("--max-steps", type=_positive_int, default=1000)
    p.add_argument(
        "--every", type=_positive_int, default=1, help="keep one frame every N steps, plus the last"
    )
    p.add_argument(
        "--eye", action="store_true", help="outline the cell the eye runs next in every frame"
    )
    p.add_argument(
        "--frame-ms", type=int, default=100, help="milliseconds per frame in a .gif"
    )
    p.set_defaults(func=_cmd_trace)

    args = parser.parse_args(argv)
    command: Callable[[argparse.Namespace], int] = args.func
    try:
        return command(args)
    except VonalError as exc:
        print(f"vonal: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnidentifiedImageError) as exc:
        # A missing/unreadable file, or an image Pillow cannot identify --
        # not a Vonal-level fault, but still not a traceback the user should
        # see. Anything else genuinely unexpected keeps propagating.
        print(f"vonal: {exc}", file=sys.stderr)
        return 1
