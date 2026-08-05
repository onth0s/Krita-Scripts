import os

import pytest

from krita_pie_menu import logger


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    target = str(tmp_path / "krita_scripts.log")
    monkeypatch.setattr(logger, "LOG_FILE_PATH", target)
    return target


def test_log_info_writes_level_and_module(log_path):
    logger.log_info("test_module", "hello world")
    content = open(log_path, encoding="utf-8").read()
    assert "[INFO]" in content
    assert "[test_module]" in content
    assert "hello world" in content


def test_log_warning_and_error_levels(log_path):
    logger.log_warning("w", "careful")
    logger.log_error("e", "boom")
    content = open(log_path, encoding="utf-8").read()
    assert "[WARNING]" in content and "[w]" in content and "careful" in content
    assert "[ERROR]" in content and "[e]" in content and "boom" in content


def test_log_error_embeds_exception_traceback(log_path):
    try:
        raise ValueError("kaput")
    except ValueError as exc:
        logger.log_error("e", "context", exc)
    content = open(log_path, encoding="utf-8").read()
    assert "Exception trace:" in content
    assert "ValueError: kaput" in content


def test_rotation_replaces_large_file(log_path, monkeypatch):
    monkeypatch.setattr(logger, "MAX_LOG_BYTES", 40)
    logger.log_info("a", "0123456789" * 8)  # > 40 bytes -> will rotate next write
    logger.log_info("b", "after rotation")

    content = open(log_path, encoding="utf-8").read()
    assert "[a]" not in content
    assert "[b]" in content

    old_path = log_path + ".old"
    assert os.path.exists(old_path)
    assert "[a]" in open(old_path, encoding="utf-8").read()


def test_logger_never_raises_on_bad_path(monkeypatch):
    monkeypatch.setattr(logger, "LOG_FILE_PATH", os.path.join(os.pathsep * 3, "nope", "dir", "f.log"))
    logger.log_info("m", "should be swallowed")
    logger.log_error("m", "boom", ValueError("x"))


def test_rotation_failure_swallowed(monkeypatch, tmp_path):
    # Make rotation's os.rename fail by pointing .old at a directory.
    target = tmp_path / "log.txt"
    target.write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr(logger, "LOG_FILE_PATH", str(target))
    monkeypatch.setattr(logger, "MAX_LOG_BYTES", 10)
    os.makedirs(str(target) + ".old", exist_ok=True)
    logger.log_info("m", "must not crash")
