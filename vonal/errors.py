"""Every Vonal error carries the position it occurred at."""


class VonalError(Exception):
    """Base for every error the toolchain raises."""


class CompileError(VonalError):
    """A fault in .vsr source text."""

    def __init__(self, line: int, col: int, message: str):
        self.line = line
        self.col = col
        super().__init__(f"line {line}, col {col}: {message}")


class _CellError(VonalError):
    def __init__(self, x: int, y: int, message: str):
        self.x = x
        self.y = y
        super().__init__(f"cell ({x},{y}): {message}")


class LoadError(_CellError):
    """A plate that cannot be decoded into a valid program."""


class VonalRuntimeError(_CellError):
    """A fault raised while executing a cell."""
