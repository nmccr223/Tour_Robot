from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class EyeDirection:
    """Simple enum-like class for gaze directions.

    Values are plain strings to keep debugging simple.
    """

    CENTER = "center"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UP_LEFT = "up_left"
    UP_RIGHT = "up_right"
    DOWN_LEFT = "down_left"
    DOWN_RIGHT = "down_right"


class EyeMood:
    """Enum-like class for moods/expressions."""

    DEFAULT = "default"
    HAPPY = "happy"
    TIRED = "tired"
    ANGRY = "angry"


@dataclass
class EyeConfig:
    """Configuration for the eyes geometry and behavior.

    Width and height are defined once and applied symmetrically to both
    eyes to keep configuration simple and intuitive for users.
    """

    eye_width: int = 180
    eye_height: int = 120
    space_between: int = 60
    corner_radius: int = 40
    pupil_radius: int = 22
    # Optional central pupil drawn on top of the main pupil.
    center_pupil_enabled: bool = False
    center_pupil_radius: int = 10
    center_pupil_color: QtGui.QColor | None = None


class EyesWidget(QtWidgets.QWidget):
    """Custom widget that draws a pair of animated robot eyes.

    The eyes are drawn as rounded rectangles ("rectangular eye shape with
    rounded corners") with circular pupils inside. The widget exposes a
    simple API for mood, gaze direction, and automatic blinking.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._config = EyeConfig()

        # State
        self._direction: str = EyeDirection.CENTER
        self._mood: str = EyeMood.DEFAULT
        self._blink_progress: float = 0.0  # 0=eyes open, 1=fully closed
        self._is_blinking: bool = False

        # Autoblink configuration
        self._autoblink_enabled: bool = True
        self._autoblink_interval_ms: int = 4000
        self._autoblink_variation_ms: int = 1500

        # Idle gaze configuration (small shifts in direction over time)
        self._idle_enabled: bool = True
        self._idle_interval_ms: int = 2000
        self._idle_variation_ms: int = 800

        # Timers
        self._blink_timer = QtCore.QTimer(self)
        self._blink_timer.timeout.connect(self._update_blink)
        self._blink_timer.setInterval(30)  # ~33 FPS

        self._autoblink_timer = QtCore.QTimer(self)
        self._autoblink_timer.timeout.connect(self._trigger_autoblink)

        self._idle_timer = QtCore.QTimer(self)
        self._idle_timer.timeout.connect(self._idle_step)

        self.setMinimumHeight(180)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)

        self._restart_autoblink_timer()
        self._restart_idle_timer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_eye_size(self, width: int, height: int) -> None:
        """Set the size of both eyes together (symmetric)."""
        self._config.eye_width = max(40, width)
        self._config.eye_height = max(30, height)
        self.update()

    def set_space_between(self, pixels: int) -> None:
        self._config.space_between = max(10, pixels)
        self.update()

    def set_corner_radius(self, radius: int) -> None:
        self._config.corner_radius = max(0, radius)
        self.update()

    def set_pupil_radius(self, radius: int) -> None:
        self._config.pupil_radius = max(4, radius)
        self.update()

    def set_center_pupil_enabled(self, enabled: bool) -> None:
        """Enable or disable drawing of a small central pupil highlight."""
        self._config.center_pupil_enabled = bool(enabled)
        self.update()

    def set_center_pupil_radius(self, radius: int) -> None:
        """Set radius (size) of the optional central pupil."""
        self._config.center_pupil_radius = max(2, radius)
        self.update()

    def set_center_pupil_color(self, color: QtGui.QColor | str | None) -> None:
        """Set color of the central pupil; None uses a default highlight color."""
        if isinstance(color, str):
            self._config.center_pupil_color = QtGui.QColor(color)
        else:
            self._config.center_pupil_color = color
        self.update()

    def set_direction(self, direction: str) -> None:
        """Set the gaze direction (up/down/left/right/.../center)."""

        # Validate direction with a simple whitelist; default to center.
        valid = {
            EyeDirection.CENTER,
            EyeDirection.UP,
            EyeDirection.DOWN,
            EyeDirection.LEFT,
            EyeDirection.RIGHT,
            EyeDirection.UP_LEFT,
            EyeDirection.UP_RIGHT,
            EyeDirection.DOWN_LEFT,
            EyeDirection.DOWN_RIGHT,
        }
        self._direction = direction if direction in valid else EyeDirection.CENTER
        self.update()

    def set_mood(self, mood: str) -> None:
        """Set the overall mood/expression (default/happy/tired/angry)."""

        valid = {EyeMood.DEFAULT, EyeMood.HAPPY, EyeMood.TIRED, EyeMood.ANGRY}
        self._mood = mood if mood in valid else EyeMood.DEFAULT
        self.update()

    def set_autoblink(self, enabled: bool,
                       interval_ms: int = 4000,
                       variation_ms: int = 1500) -> None:
        self._autoblink_enabled = bool(enabled)
        self._autoblink_interval_ms = max(500, interval_ms)
        self._autoblink_variation_ms = max(0, variation_ms)
        self._restart_autoblink_timer()

    def set_idle_mode(self, enabled: bool,
                      interval_ms: int = 2000,
                      variation_ms: int = 800) -> None:
        self._idle_enabled = bool(enabled)
        self._idle_interval_ms = max(500, interval_ms)
        self._idle_variation_ms = max(0, variation_ms)
        self._restart_idle_timer()

    def blink(self) -> None:
        """Trigger a single blink animation."""
        if self._is_blinking:
            return
        self._is_blinking = True
        self._blink_progress = 0.0
        self._blink_timer.start()

    # ------------------------------------------------------------------
    # Internal timers & state updates
    # ------------------------------------------------------------------

    def _restart_autoblink_timer(self) -> None:
        if not self._autoblink_enabled:
            self._autoblink_timer.stop()
            return
        import random

        base = self._autoblink_interval_ms
        var = self._autoblink_variation_ms
        delay = base + random.randint(-var, var) if var > 0 else base
        delay = max(500, delay)
        self._autoblink_timer.start(delay)

    def _restart_idle_timer(self) -> None:
        if not self._idle_enabled:
            self._idle_timer.stop()
            return
        import random

        base = self._idle_interval_ms
        var = self._idle_variation_ms
        delay = base + random.randint(-var, var) if var > 0 else base
        delay = max(400, delay)
        self._idle_timer.start(delay)

    def _trigger_autoblink(self) -> None:
        self.blink()
        self._restart_autoblink_timer()

    def _idle_step(self) -> None:
        """Occasional small gaze change when idle."""
        import random

        if not self._idle_enabled:
            return

        # 50% chance to return to center, 50% to pick a random direction.
        if random.random() < 0.5:
            self.set_direction(EyeDirection.CENTER)
        else:
            directions = [
                EyeDirection.UP,
                EyeDirection.DOWN,
                EyeDirection.LEFT,
                EyeDirection.RIGHT,
                EyeDirection.UP_LEFT,
                EyeDirection.UP_RIGHT,
                EyeDirection.DOWN_LEFT,
                EyeDirection.DOWN_RIGHT,
            ]
            self.set_direction(random.choice(directions))

        self._restart_idle_timer()

    def _update_blink(self) -> None:
        # Simple triangular blink: close then open.
        step = 0.12  # blink speed
        self._blink_progress += step
        if self._blink_progress >= 2.0:
            # End of blink cycle
            self._blink_progress = 0.0
            self._is_blinking = False
            self._blink_timer.stop()
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        cfg = self._config

        # Compute total width and positions.
        total_eye_width = cfg.eye_width * 2 + cfg.space_between
        x_start = rect.center().x() - total_eye_width // 2
        center_y = rect.center().y()

        # Left and right eye rectangles.
        left_rect = QtCore.QRect(
            x_start,
            center_y - cfg.eye_height // 2,
            cfg.eye_width,
            cfg.eye_height,
        )
        right_rect = QtCore.QRect(
            x_start + cfg.eye_width + cfg.space_between,
            center_y - cfg.eye_height // 2,
            cfg.eye_width,
            cfg.eye_height,
        )

        # Choose color scheme based on mood.
        eye_color = QtGui.QColor("#FFFFFF")
        outline_color = QtGui.QColor("#222222")
        pupil_color = QtGui.QColor("#000000")

        if self._mood == EyeMood.HAPPY:
            outline_color = QtGui.QColor("#228833")
        elif self._mood == EyeMood.TIRED:
            outline_color = QtGui.QColor("#AA8844")
        elif self._mood == EyeMood.ANGRY:
            outline_color = QtGui.QColor("#CC2222")

        # Draw eyes.
        self._draw_eye(painter, left_rect, eye_color, outline_color, pupil_color, is_left=True)
        self._draw_eye(painter, right_rect, eye_color, outline_color, pupil_color, is_left=False)

    def _draw_eye(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        eye_color: QtGui.QColor,
        outline_color: QtGui.QColor,
        pupil_color: QtGui.QColor,
        *,
        is_left: bool,
    ) -> None:
        cfg = self._config

        # Base eye background.
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, cfg.corner_radius, cfg.corner_radius)

        painter.setPen(QtGui.QPen(outline_color, 4))
        painter.setBrush(eye_color)
        painter.drawPath(path)

        # Compute pupil center based on direction.
        cx = rect.center().x()
        cy = rect.center().y()
        dx, dy = self._direction_offset(rect)
        pupil_center = QtCore.QPointF(cx + dx, cy + dy)

        # Eyelid effect from blinking or tired mood.
        openness = self._compute_openness()

        # Draw pupil only in the open area.
        pupil_radius = cfg.pupil_radius
        pupil_rect = QtCore.QRectF(
            pupil_center.x() - pupil_radius,
            pupil_center.y() - pupil_radius,
            2 * pupil_radius,
            2 * pupil_radius,
        )

        # Clip to simulate eyelids closing.
        painter.save()
        eyelid_clip = QtCore.QRectF(rect)
        # Reduce visible height based on openness (0..1).
        visible_height = rect.height() * openness
        top = rect.center().y() - visible_height / 2.0
        eyelid_clip.setTop(top)
        eyelid_clip.setHeight(visible_height)
        painter.setClipRect(eyelid_clip)

        painter.setBrush(pupil_color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(pupil_rect)
        painter.restore()

        # Optional central pupil overlay (e.g. highlight/iris detail).
        if cfg.center_pupil_enabled:
            center_radius = min(cfg.center_pupil_radius, pupil_radius - 1)
            if center_radius > 1:
                center_rect = QtCore.QRectF(
                    pupil_center.x() - center_radius,
                    pupil_center.y() - center_radius,
                    2 * center_radius,
                    2 * center_radius,
                )
                color = cfg.center_pupil_color or QtGui.QColor("#333333")
                painter.save()
                painter.setBrush(color)
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(center_rect)
                painter.restore()

        # Optionally draw a top eyelid line when mostly closed.
        if openness < 0.4:
            y = rect.center().y() - rect.height() * (0.5 - openness / 2.0)
            painter.setPen(QtGui.QPen(outline_color, 6))
            painter.drawLine(rect.left() + 8, int(y), rect.right() - 8, int(y))

    def _direction_offset(self, rect: QtCore.QRect) -> tuple[float, float]:
        """Return (dx, dy) offset for pupil center based on direction."""

        # Movement limits as fraction of eye size.
        max_dx = rect.width() * 0.18
        max_dy = rect.height() * 0.18

        dx = 0.0
        dy = 0.0

        if self._direction in (EyeDirection.LEFT, EyeDirection.UP_LEFT, EyeDirection.DOWN_LEFT):
            dx = -max_dx
        elif self._direction in (EyeDirection.RIGHT, EyeDirection.UP_RIGHT, EyeDirection.DOWN_RIGHT):
            dx = max_dx

        if self._direction in (EyeDirection.UP, EyeDirection.UP_LEFT, EyeDirection.UP_RIGHT):
            dy = -max_dy
        elif self._direction in (EyeDirection.DOWN, EyeDirection.DOWN_LEFT, EyeDirection.DOWN_RIGHT):
            dy = max_dy

        return dx, dy

    def _compute_openness(self) -> float:
        """Compute eye openness (0=closed, 1=open) from blink + mood."""

        # Blink openness: 1 -> 0 -> 1 over the blink cycle.
        blink_factor = 1.0
        if self._is_blinking:
            # First half: closing, second half: opening.
            if self._blink_progress <= 1.0:
                blink_factor = max(0.0, 1.0 - self._blink_progress)
            else:
                blink_factor = max(0.0, self._blink_progress - 1.0)

        # Mood-based baseline (tired eyes are more closed).
        mood_factor = 1.0
        if self._mood == EyeMood.TIRED:
            mood_factor = 0.6
        elif self._mood == EyeMood.ANGRY:
            mood_factor = 0.85

        openness = blink_factor * mood_factor
        # Clamp for safety.
        return max(0.0, min(1.0, openness))
