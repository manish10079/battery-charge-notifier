"""Entry point: application bootstrap and the single-instance gate.

``python -m battery_charge_notifier`` and the ``battery_charge_notifier`` console script both land
here. The sequence is:

1. create the ``QApplication`` and pin the quit behaviour down
2. claim the single-instance lock, or hand over to the instance that owns it
3. build the object graph through :class:`~battery_charge_notifier.controller.AppController`
4. start monitoring and run the event loop
"""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from . import __version__, colors, resources
from .controller import AppController
from .single_instance import COMMAND_SHOW_SETTINGS, SingleInstance

logger = logging.getLogger(__name__)

APP_NAME = "Battery Charge Notifier"
ORGANISATION_NAME = "Battery Charge Notifier"


def configure_logging(verbose: bool = False) -> None:
    """Set up console logging.

    Args:
        verbose: When ``True``, log at ``DEBUG`` instead of ``INFO``.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog="battery-charge-notifier",
        description=(
            "Watch the battery and remind you when to unplug or plug in the charger. "
            "Battery Charge Notifier only reads battery status and never controls charging."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--show-settings",
        action="store_true",
        help="Open the settings dialog immediately after starting the first instance.",
    )
    parser.add_argument(
        "--no-startup-sync",
        action="store_true",
        help=(
            "Do not create or update the launch-at-login entry. Useful when running "
            "from a shell you do not want to persist."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def create_application(argv: list[str]) -> QApplication:
    """Create and configure the ``QApplication``.

    Args:
        argv: Arguments handed to Qt.

    Returns:
        The application instance, with quit-on-last-window-closed disabled so
        that closing the settings dialog or the popup never exits the process.
    """
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(ORGANISATION_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(resources.load_icon(resources.APP_ICON))
    colors.apply_system_theme(app)
    return app


def main(argv: list[str] | None = None) -> int:
    """Run Battery Charge Notifier.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
    args = parse_args(argv)
    configure_logging(args.verbose)

    app = create_application([sys.argv[0], *(argv or [])])

    # Only one instance may own the tray icon and the monitor.
    gate = SingleInstance()
    if not gate.try_acquire():
        logger.info("Another Battery Charge Notifier instance is already running; handing over")
        gate.notify_running_instance(COMMAND_SHOW_SETTINGS)
        return 0

    controller = AppController(
        app,
        single_instance=gate,
        sync_startup=not args.no_startup_sync,
    )
    controller.quitRequested.connect(app.quit)
    app.aboutToQuit.connect(controller.shutdown)

    controller.start()
    if args.show_settings:
        controller.open_settings()

    return app.exec()


if __name__ == "__main__":  # pragma: no cover - module execution entry point
    raise SystemExit(main())
