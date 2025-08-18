from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import threading
import traceback


class FileLogger:
    """File-based logger writing to general.log and error.log with ISO-8601 timestamps.

    - Writes INFO/DEBUG to logs/general.log
    - Writes ERROR (with optional traceback) to logs/error.log
    - Ensures the logs directory exists
    - Thread-safe appends
    """

    def __init__(self, logs_dir: Path | str = Path("logs")) -> None:
        """Initialize the FileLogger with specified logs directory.
        
        Args:
            logs_dir: Directory path where log files will be created. Defaults to "logs".
                     Can be a Path object or string.
                     
        Raises:
            OSError: If the logs directory cannot be created due to permissions or invalid path.
        """
        self._dir = Path(logs_dir)
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OSError(f"Cannot create logs directory '{self._dir}': {e}") from e
        self._general = self._dir / "general.log"
        self._error = self._dir / "error.log"
        self._lock = threading.RLock()

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _write(self, path: Path, level: str, message: str, exc: Optional[Exception] = None) -> None:
        """Write log entry to file with timestamp and optional exception traceback.
        
        Args:
            path: Path to the log file where the entry will be written.
            level: Log level string (e.g., "INFO", "DEBUG", "ERROR").
            message: The log message to write.
            exc: Optional exception to include traceback information. Defaults to None.
            
        Note:
            If writing to the log file fails, the error is silently ignored to prevent
            logging failures from breaking the application.
        """
        line = f"{self._get_timestamp()} [{level}] {message}"
        with self._lock:
            try:
                with path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    if exc is not None:
                        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                        f.write(f"{self._get_timestamp()} [TRACE] {tb}\n")
            except OSError:
                # Silently ignore file write failures to prevent logging from breaking the app
                # This could happen due to disk full, permissions, etc.
                pass

    def info(self, message: str) -> None:
        """Write an INFO level message to the general log file.
        
        Args:
            message: The informational message to log.
        """
        self._write(self._general, "INFO", message)

    def debug(self, message: str) -> None:
        """Write a DEBUG level message to the general log file.
        
        Args:
            message: The debug message to log.
        """
        self._write(self._general, "DEBUG", message)

    def error(self, message: str, *, exc: Optional[Exception] = None) -> None:
        """Write an ERROR level message to the error log file.
        
        Args:
            message: The error message to log.
            exc: Optional exception to include traceback information. Defaults to None.
        """
        self._write(self._error, "ERROR", message, exc)