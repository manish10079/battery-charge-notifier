"""Generate the bundled app and tray icons.

Run this once (``python tools/generate_assets.py``) after changing the icon
design or the design tokens; the generated files under
``battery_charge_notifier/assets/`` are committed and shipped as package data, so the
application never needs to draw its own icons at runtime.

Every colour comes from :mod:`battery_charge_notifier.colors`, keeping the "one place for
colour" rule intact even for generated art.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from battery_charge_notifier import colors  # noqa: E402

ASSETS = PROJECT_ROOT / "battery_charge_notifier" / "assets"

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Spin box arrow bitmaps, drawn 4x their display size.
ARROW_W = 36
ARROW_H = 24


def _color(token: str, alpha: int = 255) -> QColor:
    """Build a QColor from a hex token."""
    value = QColor(token)
    value.setAlpha(alpha)
    return value


def _chevron_path(cx: float, cy: float, width: float, height: float, pointing_up: bool) -> QPainterPath:
    """Build a filled triangle centred on ``(cx, cy)``."""
    path = QPainterPath()
    half_w = width / 2
    half_h = height / 2
    if pointing_up:
        path.moveTo(cx, cy - half_h)
        path.lineTo(cx + half_w, cy + half_h)
        path.lineTo(cx - half_w, cy + half_h)
    else:
        path.moveTo(cx, cy + half_h)
        path.lineTo(cx + half_w, cy - half_h)
        path.lineTo(cx - half_w, cy - half_h)
    path.closeSubpath()
    return path


def draw_arrow(pointing_up: bool, token: str) -> QImage:
    """Render a small filled chevron used by spin box buttons.

    Args:
        pointing_up: Direction the arrow points.
        token: Colour token.

    Returns:
        A premultiplied ARGB image, drawn oversized so Qt scales it down
        smoothly on high-DPI displays.
    """
    image = QImage(ARROW_W, ARROW_H, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(token))
    painter.drawPath(
        _chevron_path(
            ARROW_W / 2,
            ARROW_H / 2,
            ARROW_W * 0.88,
            ARROW_H * 0.84,
            pointing_up=pointing_up,
        )
    )
    painter.end()
    return image


def draw_battery(
    size: int,
    *,
    accent: str,
    fill_ratio: float,
    chevron: str | None = None,
    chevron_color: str | None = None,
) -> QImage:
    """Render a battery glyph.

    Args:
        size: Square canvas size in pixels.
        accent: Token for the charged portion of the battery.
        fill_ratio: Fraction of the battery that is filled, 0.0-1.0.
        chevron: ``None``, ``"up"`` (unplug) or ``"down"`` (plug in).
        chevron_color: Token for the chevron; defaults to the accent.

    Returns:
        A premultiplied ARGB image.
    """
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    unit = size / 32.0  # design grid: every dimension below assumes a 32px icon
    margin = 3.0 * unit
    nub_w = 2.4 * unit
    nub_h = 8.0 * unit
    stroke = max(1.0, 2.6 * unit)

    body = QRectF(
        margin,
        margin + 2.0 * unit,
        size - 2 * margin - nub_w,
        size - 2 * margin - 4.0 * unit,
    )
    radius = 3.6 * unit

    # Outer shell.
    shell = QPainterPath()
    shell.addRoundedRect(body, radius, radius)
    painter.setPen(QPen(_color(colors.ICON_FOREGROUND), stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(shell)

    # Terminal nub on the right-hand side.
    nub = QRectF(body.right(), body.center().y() - nub_h / 2, nub_w, nub_h)
    nub_path = QPainterPath()
    nub_path.addRoundedRect(nub, unit, unit)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(colors.ICON_FOREGROUND))
    painter.drawPath(nub_path)

    # Charge level.
    inset = stroke * 1.15
    track = body.adjusted(inset, inset, -inset, -inset)
    if fill_ratio > 0.0:
        filled = QRectF(track)
        filled.setWidth(max(track.height() * 0.4, track.width() * min(1.0, fill_ratio)))
        fill_path = QPainterPath()
        fill_path.addRoundedRect(filled, radius * 0.45, radius * 0.45)
        painter.setBrush(_color(accent))
        painter.drawPath(fill_path)

    if chevron is not None:
        token = chevron_color or accent
        marker = _chevron_path(
            body.right() - 5.0 * unit,
            body.top() + 5.0 * unit,
            6.0 * unit,
            5.0 * unit,
            pointing_up=chevron == "up",
        )
        painter.setBrush(_color(token))
        painter.drawPath(marker)

    painter.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    """Serialise *image* to PNG bytes."""
    # The QByteArray must outlive the QBuffer: QBuffer only keeps a pointer to it.
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Failed to encode PNG")
    buffer.close()
    return bytes(data)


def write_ico(path: Path, images: list[QImage]) -> None:
    """Write a PNG-compressed multi-size ``.ico`` file.

    Modern Windows (Vista and later) accepts PNG payloads inside the ICO
    container, which keeps this dependency-free.

    Args:
        path: Destination file.
        images: Square images to embed, at their native sizes.
    """
    payloads = [(image.width(), _png_bytes(image)) for image in images]
    count = len(payloads)

    header = struct.pack("<HHH", 0, 1, count)
    directory = bytearray()
    offset = 6 + 16 * count

    for width, payload in payloads:
        dimension = 0 if width >= 256 else width
        directory += struct.pack(
            "<BBBBHHII",
            dimension,  # width
            dimension,  # height
            0,  # palette count
            0,  # reserved
            1,  # colour planes
            32,  # bits per pixel
            len(payload),
            offset,
        )
        offset += len(payload)

    path.write_bytes(header + bytes(directory) + b"".join(p for _, p in payloads))


def main() -> int:
    """Generate every bundled icon and report the results."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)

    # Neutral application icon: a healthy, partially charged battery.
    app_icon = draw_battery(256, accent=colors.ACCENT_OK, fill_ratio=0.62)
    app_icon.save(str(ASSETS / "app.png"), "PNG")
    write_ico(
        ASSETS / "app.ico",
        [draw_battery(size, accent=colors.ACCENT_OK, fill_ratio=0.62) for size in ICO_SIZES],
    )

    # Tray variants. The accent carries the meaning; the chevron reinforces it.
    # The chevron is drawn in whichever colour contrasts with what is underneath
    # it: knocked out of the fill when the battery is nearly full, and in the
    # accent when the battery is nearly empty.
    variants = {
        "tray_ok.png": dict(accent=colors.ACCENT_OK, fill_ratio=0.62, chevron=None),
        "tray_unplug.png": dict(
            accent=colors.ACCENT_UNPLUG,
            fill_ratio=0.9,
            chevron="up",
            chevron_color=colors.ICON_BACKGROUND,
        ),
        "tray_plug.png": dict(
            accent=colors.ACCENT_PLUG,
            fill_ratio=0.2,
            chevron="down",
            chevron_color=colors.ACCENT_PLUG,
        ),
        "tray_paused.png": dict(
            accent=colors.TEXT_MUTED, fill_ratio=0.5, chevron=None
        ),
    }
    for name, options in variants.items():
        draw_battery(64, **options).save(str(ASSETS / name), "PNG")

    # Qt style sheets cannot draw a triangle from borders, so the spin box
    # arrows are real bitmaps.
    draw_arrow(pointing_up=True, token=colors.TEXT_SECONDARY).save(
        str(ASSETS / "arrow_up.png"), "PNG"
    )
    draw_arrow(pointing_up=False, token=colors.TEXT_SECONDARY).save(
        str(ASSETS / "arrow_down.png"), "PNG"
    )

    for produced in sorted(ASSETS.iterdir()):
        print(f"{produced.name:16} {produced.stat().st_size:>8} bytes")

    # Keep the application alive until every QImage and QPainter is gone.
    _ = app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
