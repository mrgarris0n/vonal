from vonal import errors


def test_compile_error_reports_line_and_column():
    e = errors.CompileError(4, 11, "bad scale digit")
    assert e.line == 4 and e.col == 11
    assert "line 4, col 11" in str(e)
    assert "bad scale digit" in str(e)


def test_load_and_runtime_errors_report_the_cell():
    for cls in (errors.LoadError, errors.VonalRuntimeError):
        e = cls(2, 7, "boom")
        assert (e.x, e.y) == (2, 7)
        assert "cell (2,7)" in str(e)


def test_all_errors_share_a_base():
    for cls in (errors.CompileError, errors.LoadError, errors.VonalRuntimeError):
        assert issubclass(cls, errors.VonalError)
