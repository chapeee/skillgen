import logging
from datetime import datetime, timezone

from skillgen.cli import main
from skillgen.logs import choose_console_level, list_logs, make_log_path, prune_logs, start_logging
from skillgen.workspace import WORKSPACE_DIR


def test_choose_console_level_follows_verbosity():
    assert choose_console_level(0) == logging.WARNING
    assert choose_console_level(1) == logging.INFO
    assert choose_console_level(5) == logging.DEBUG


def test_make_log_path_names_by_time_and_command(tmp_path):
    when = datetime(2026, 10, 8, 9, 15, 0, tzinfo=timezone.utc)
    assert (
        make_log_path(tmp_path, "generate", when)
        == tmp_path / "logs" / "20261008-091500-generate.log"
    )


def test_prune_logs_keeps_newest(tmp_path):
    (tmp_path / "logs").mkdir()
    for index in range(5):
        (tmp_path / "logs" / f"2026100{index}-000000-x.log").write_text("")
    prune_logs(tmp_path, keep=2)
    assert [p.name for p in list_logs(tmp_path)] == [
        "20261004-000000-x.log",
        "20261003-000000-x.log",
    ]


def test_start_logging_writes_file_inside_workspace(tmp_path):
    path = start_logging(0, tmp_path, "routes", ["routes", "--all"])
    logging.getLogger("skillgen.test").debug("detail for the file only")
    assert path is not None and path.parent == tmp_path / "logs"
    text = path.read_text(encoding="utf-8")
    assert "routes --all" in text and "detail for the file only" in text
    assert start_logging(0, None, "doctor", []) is None


def test_every_command_leaves_a_log_and_logs_shows_it(tmp_path, capsys):
    assert main(["init", "--root", str(tmp_path), "--app-name", "Shop"]) == 0
    assert main(["questions", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["logs", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "Latest log:" in output and "questions finished" in output
    assert (tmp_path / WORKSPACE_DIR / ".gitignore").read_text().count("logs/") == 1


def test_repeated_cli_calls_close_file_handlers_before_return(tmp_path, capsys):
    assert main(["init", "--root", str(tmp_path), "--app-name", "Shop"]) == 0
    assert not any(
        isinstance(handler, logging.FileHandler) for handler in logging.getLogger().handlers
    )
    assert main(["questions", "--root", str(tmp_path)]) == 0
    assert not any(
        isinstance(handler, logging.FileHandler) for handler in logging.getLogger().handlers
    )
    capsys.readouterr()
    for path in list_logs(tmp_path / WORKSPACE_DIR):
        path.unlink()


def test_errors_point_to_the_log(tmp_path, capsys):
    main(["init", "--root", str(tmp_path)])
    capsys.readouterr()
    assert main(["answer", "q000000", "yes", "--root", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "error: no question" in error and "Full log:" in error
