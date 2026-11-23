"""Entry point: ``ai-mod-painter [root folder]``."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ai_mod_painter import APP_NAME, __version__
from ai_mod_painter.ui.main_window import MainWindow

ORGANIZATION = "ai-mod-painter"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if any(arg in ("-h", "--help") for arg in argv[1:]):
        print(f"usage: ai-mod-painter [ROOT_FOLDER]\n\n{APP_NAME} {__version__}")
        return 0
    if any(arg == "--version" for arg in argv[1:]):
        print(__version__)
        return 0

    app = QApplication.instance() or QApplication(argv)
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()
    folders = [arg for arg in argv[1:] if not arg.startswith("-")]
    if folders:
        window.open_root(Path(folders[0]))
    else:
        window.restore_root()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
