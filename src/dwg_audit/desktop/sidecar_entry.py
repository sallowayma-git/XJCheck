from __future__ import annotations

import sys

from dwg_audit.cli import run


def _configure_text_stream_utf8(stream) -> None:
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="strict")


def main() -> None:
    # PyInstaller's windowed executable inherits the Windows ANSI code page for
    # synchronous CLI output. Rust expects JSON bytes to be UTF-8.
    _configure_text_stream_utf8(sys.stdout)
    _configure_text_stream_utf8(sys.stderr)
    run()


if __name__ == "__main__":
    main()
