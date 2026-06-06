import logging

from dbdocs.core.log import LogFormatter, logger


def test_logger_is_configured_with_color_formatter():
    assert logger.name == "dbdocs"
    assert logger.level == logging.DEBUG
    # The import-time guard attaches a StreamHandler using our color formatter.
    assert any(isinstance(h.formatter, LogFormatter) for h in logger.handlers)


def test_formatter_colors_each_level():
    formatter = LogFormatter()
    for level in (
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ):
        record = logging.LogRecord(
            name="dbterd",
            level=level,
            pathname=__file__,
            lineno=10,
            msg="hello",
            args=(),
            exc_info=None,
        )
        rendered = formatter.format(record)
        assert "hello" in rendered
        # Each level wraps the message in an ANSI color + reset.
        assert "\x1b[" in rendered
        assert rendered.endswith("\x1b[0m")
