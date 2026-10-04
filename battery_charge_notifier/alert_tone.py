"""Looping warning tone that follows the popup's lifetime.

The tone starts when the popup appears and is stopped as soon as the popup
begins to dismiss (snooze, Dismiss, Esc, timeout, or charger auto-dismiss).
Playback is best-effort: a missing asset or a session without audio simply
stays silent.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from . import resources

logger = logging.getLogger(__name__)

ALERT_TONE = "alert.mp3"


class AlertTone(QObject):
    """Plays the bundled alert MP3 on a loop until :meth:`stop`."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player: QMediaPlayer | None = None
        path = resources.asset_path(ALERT_TONE)
        if not path.is_file():
            logger.warning("Alert tone asset is missing (looked in %s)", path.parent)
            return
        audio = QAudioOutput(self)
        audio.setVolume(0.55)
        player = QMediaPlayer(self)
        player.setAudioOutput(audio)
        player.setSource(QUrl.fromLocalFile(str(path)))
        player.setLoops(-1)
        self._player = player

    def start(self) -> None:
        """Begin looping playback if the player loaded."""
        player = self._player
        if player is None:
            return
        if player.error() != QMediaPlayer.Error.NoError:
            logger.warning("Alert tone could not be loaded: %s", player.errorString())
            return
        if player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            player.play()

    def stop(self) -> None:
        """Silence the tone immediately."""
        if self._player is not None:
            self._player.stop()

    def is_playing(self) -> bool:
        """Whether Qt reports the player as currently playing."""
        return (
            self._player is not None
            and self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        )


__all__ = ["ALERT_TONE", "AlertTone"]
