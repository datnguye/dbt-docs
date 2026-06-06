import logging
from pathlib import Path

#: Where the DEBUG-level file log is streamed (relative to the working dir).
LOG_FILE = Path("logs") / "dbdocs.log"
#: Plain (non-ANSI) line format for the file — colour codes don't belong in a file.
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"


class LogFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# Named "dbdocs" (not "dbterd") so our handler/level config doesn't collide with
# the dbterd library's own logger of the same name.
logger = logging.getLogger("dbdocs")
logger.setLevel(logging.DEBUG)
# Emit only through our own handlers. Without this, records also propagate to the
# root logger — which dbterd configures via basicConfig — producing duplicate,
# differently-formatted "INFO:dbdocs:…" lines.
logger.propagate = False

if len(logger.handlers) == 0:  # pragma: no cover - import-time handler guard
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(LogFormatter())
    logger.addHandler(ch)

    # Stream everything (DEBUG and up) to logs/dbdocs.log too. Best-effort: if the
    # logs dir can't be created/written (read-only fs), the console handler still
    # works and we don't crash on import.
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(FILE_FORMAT))
        logger.addHandler(fh)
    except OSError:
        pass
