"""compile / disassemble / run / trace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from vonal import decode, notation, render
from vonal.cell import Cell, Plate
from vonal.errors import VonalError
from vonal.machine import Machine


def _load(path: Path) -> Plate:
    """A .vsr is compiled in memory; anything else is decoded as an image."""
    if path.suffix == ".vsr":
        return notation.parse(path.read_text())
    return decode.decode(Image.open(path))


def _with_field(plate: Plate, field: list[list[int]]) -> Plate:
    """The plate as the running machine has deformed it."""
    current = plate
    for y, row in enumerate(field):
        for x, value in enumerate(row):
            cell = current.at(x, y)
            if cell.scale != value and not cell.is_void:
                current = current.replaced(
                    x, y, Cell(cell.form, cell.variant, value, cell.ground)
                )
    return current


def _cmd_compile(args: argparse.Namespace) -> int:
    render.render(notation.parse(Path(args.source).read_text())).save(args.out)
    return 0


def _cmd_disassemble(args: argparse.Namespace) -> int:
    text = notation.emit(decode.decode(Image.open(args.image)))
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    Machine(_load(Path(args.plate))).run(max_steps=args.max_steps)
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    plate = _load(Path(args.plate))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    machine = Machine(plate)
    frame = 0
    while True:
        render.render(_with_field(plate, machine.field)).save(out / f"{frame:05d}.png")
        frame += 1
        if machine.steps >= args.max_steps or not machine.step():
            break
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vonal")
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

    p = sub.add_parser("trace", help="write one frame per step to a directory")
    p.add_argument("plate")
    p.add_argument("out")
    p.add_argument("--max-steps", type=int, default=1000)
    p.set_defaults(func=_cmd_trace)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except VonalError as exc:
        print(f"vonal: {exc}", file=sys.stderr)
        return 1
