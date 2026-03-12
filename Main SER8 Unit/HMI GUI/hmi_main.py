import json
import os
import platform
import time
from dataclasses import dataclass, asdict
from typing import List

import rclpy
from rclpy.node import Node

from PySide6 import QtCore, QtGui, QtWidgets

from eyes_widget import EyesWidget, EyeMood


DEMO_INPUT_AUTO = "auto"
DEMO_INPUT_TOUCH = "touch"
DEMO_INPUT_MOUSE = "mouse"
DEMO_INPUT_KEYBOARD = "keyboard"


def apply_touch_friendly_dialog(dialog: QtWidgets.QDialog | QtWidgets.QMessageBox) -> None:
    """Make dialogs easier to use on touch displays without harming desktop use."""
    dialog.setMinimumWidth(max(dialog.minimumWidth(), 520))

    for button in dialog.findChildren(QtWidgets.QPushButton):
        button.setMinimumHeight(56)
        button.setMinimumWidth(130)
        font = button.font()
        font.setPointSize(max(font.pointSize(), 13))
        button.setFont(font)

    for widget_type in (QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QSpinBox):
        for field in dialog.findChildren(widget_type):
            field.setMinimumHeight(42)
            font = field.font()
            font.setPointSize(max(font.pointSize(), 12))
            field.setFont(font)


def show_message_box(
    parent: QtWidgets.QWidget,
    icon: QtWidgets.QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QtWidgets.QMessageBox.StandardButtons,
    default_button: QtWidgets.QMessageBox.StandardButton,
) -> QtWidgets.QMessageBox.StandardButton:
    """Create a consistently sized message box for demo use."""
    message_box = QtWidgets.QMessageBox(parent)
    message_box.setIcon(icon)
    message_box.setWindowTitle(title)
    message_box.setText(text)
    message_box.setStandardButtons(buttons)
    message_box.setDefaultButton(default_button)
    apply_touch_friendly_dialog(message_box)
    return QtWidgets.QMessageBox.StandardButton(message_box.exec())


def run_text_input_dialog(
    parent: QtWidgets.QWidget,
    title: str,
    label: str,
    default_text: str = "",
) -> tuple[str, bool]:
    """Create a touch-friendly text input dialog."""
    dialog = QtWidgets.QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextValue(default_text)
    dialog.setInputMode(QtWidgets.QInputDialog.TextInput)
    apply_touch_friendly_dialog(dialog)
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return "", False
    return dialog.textValue(), True


class InputDeviceDetector:
    """Detects available input devices (mouse, keyboard) on the system."""
    
    def __init__(self):
        self.has_mouse = False
        self.has_keyboard = False
        self.detect_devices()
    
    def detect_devices(self):
        """Detect connected input devices."""
        if platform.system() == "Windows":
            self._detect_windows_devices()
        elif platform.system() == "Linux":
            self._detect_linux_devices()
    
    def _detect_windows_devices(self):
        """Detect input devices on Windows using Windows API."""
        try:
            # Check for mouse using Windows API
            import ctypes
            mouse_count = ctypes.windll.user32.GetSystemMetrics(75)  # SM_CMOUSEBUTTONS
            self.has_mouse = mouse_count > 0
            
            # Check for keyboard - typically always present on Windows
            keyboard_count = ctypes.windll.user32.GetSystemMetrics(26)  # SM_CXKEYBOARDKEYS
            self.has_keyboard = keyboard_count > 0
        except Exception as e:
            print(f"Error detecting Windows input devices: {e}")
    
    def _detect_linux_devices(self):
        """Detect input devices on Linux using /proc/bus/input/devices."""
        try:
            with open('/proc/bus/input/devices', 'r') as f:
                content = f.read()
                self.has_mouse = 'mouse' in content.lower()
                self.has_keyboard = 'keyboard' in content.lower()
        except Exception as e:
            print(f"Error detecting Linux input devices: {e}")
    
    def has_physical_input(self):
        """Return True if mouse or keyboard detected."""
        return self.has_mouse or self.has_keyboard

    def describe_detected_devices(self) -> str:
        """Return a human-readable summary of detected hardware."""
        detected = []
        if self.has_mouse:
            detected.append("mouse")
        if self.has_keyboard:
            detected.append("keyboard")
        if not detected:
            return "touch-only or undetected"
        return ", ".join(detected)


@dataclass
class LocationEntry:
    """Represents a single destination/location in the system.

    Fields:
        - id:          internal identifier (string) used as a stable key.
        - name:        human-readable label shown on the HMI buttons.
        - floor_plan:  optional reference to a floor plan resource
                       (e.g., image or map filename). This can be set in the
                       mapping editor.
        - apriltag_id: optional numeric AprilTag ID associated with this
                       destination (or -1 if unset).
        - nearby_tags: optional list of other AprilTag IDs that are considered
                       "near" this destination, used for planning.
    """

    id: str
    name: str
    floor_plan: str | None = None
    apriltag_id: int | None = None
    nearby_tags: List[int] | None = None


DEMO_SAMPLE_LOCATIONS = [
    LocationEntry(id="1", name="Main Lobby", floor_plan="floor_a.png", apriltag_id=11, nearby_tags=[10, 12]),
    LocationEntry(id="2", name="Reception", floor_plan="floor_a.png", apriltag_id=14, nearby_tags=[11, 15]),
    LocationEntry(id="3", name="Innovation Zone", floor_plan="floor_b.png", apriltag_id=21, nearby_tags=[20, 22]),
    LocationEntry(id="4", name="Conference Room", floor_plan="floor_b.png", apriltag_id=24, nearby_tags=[23, 25]),
    LocationEntry(id="5", name="Charging Dock", floor_plan="service_map.png", apriltag_id=31, nearby_tags=[30]),
    LocationEntry(id="6", name="Exit", floor_plan="floor_a.png", apriltag_id=16, nearby_tags=[14, 15]),
]


class LocationModel(QtCore.QObject):
    """
    Simple model that manages a list of LocationEntry objects and persists
    them to a JSON file.

    This keeps storage logic separate from the GUI and ROS logic.
    """
    locations_changed = QtCore.Signal()

    def __init__(self, storage_path: str, parent=None):
        super().__init__(parent)
        self._storage_path = storage_path
        self._locations: List[LocationEntry] = []
        self.load()

    @property
    def locations(self) -> List[LocationEntry]:
        return self._locations

    def load(self) -> None:
        """Load locations from JSON file if it exists."""
        if not os.path.exists(self._storage_path):
            self._locations = []
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._locations = []
            for entry in data:
                # Backwards compatible load: older files may only have id/name.
                loc = LocationEntry(
                    id=str(entry.get("id", "")),
                    name=str(entry.get("name", "")),
                    floor_plan=entry.get("floor_plan"),
                    apriltag_id=entry.get("apriltag_id"),
                    nearby_tags=entry.get("nearby_tags"),
                )
                self._locations.append(loc)
        except Exception as exc:
            # If file is corrupted, log and reset.
            print(f"Failed to load locations from {self._storage_path}: {exc}")
            self._locations = []

        self.locations_changed.emit()

    def save(self) -> None:
        """Save current locations to JSON file."""
        try:
            data = [asdict(loc) for loc in self._locations]
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            print(f"Failed to save locations to {self._storage_path}: {exc}")

    def _next_location_id(self) -> str:
        """Return the next unique numeric string identifier."""
        numeric_ids = []
        for location in self._locations:
            try:
                numeric_ids.append(int(location.id))
            except (TypeError, ValueError):
                continue
        return str(max(numeric_ids, default=0) + 1)

    def add_location(self, name: str) -> None:
        """Add a new location with a generated ID."""
        next_id = self._next_location_id()
        self._locations.append(LocationEntry(id=next_id, name=name))
        self.save()
        self.locations_changed.emit()

    def ensure_demo_locations(self) -> bool:
        """Seed the model with sample destinations when no data exists."""
        if self._locations:
            return False
        self._locations = [LocationEntry(**asdict(location)) for location in DEMO_SAMPLE_LOCATIONS]
        self.save()
        self.locations_changed.emit()
        return True

    def remove_location(self, loc: LocationEntry) -> None:
        """Remove a location from the list."""
        self._locations = [l for l in self._locations if l.id != loc.id]
        self.save()
        self.locations_changed.emit()

    def rename_location(self, loc: LocationEntry, new_name: str) -> None:
        """Rename an existing location."""
        for l in self._locations:
            if l.id == loc.id:
                l.name = new_name
                break
        self.save()
        self.locations_changed.emit()

    def move_location_up(self, index: int) -> None:
        """Move a location one position up in the list (if possible)."""
        if index <= 0 or index >= len(self._locations):
            return
        self._locations[index - 1], self._locations[index] = (
            self._locations[index],
            self._locations[index - 1],
        )
        self.save()
        self.locations_changed.emit()

    def move_location_down(self, index: int) -> None:
        """Move a location one position down in the list (if possible)."""
        if index < 0 or index >= len(self._locations) - 1:
            return
        self._locations[index], self._locations[index + 1] = (
            self._locations[index + 1],
            self._locations[index],
        )
        self.save()
        self.locations_changed.emit()


class LocationButton(QtWidgets.QPushButton):
    """
    Custom button widget bound to a LocationEntry.

    Supports:
      - Tap: (later) send ROS command for this location.
      - Right-click: open context menu for rename/delete.
    """
    request_rename = QtCore.Signal(LocationEntry)
    request_delete = QtCore.Signal(LocationEntry)
    request_activate = QtCore.Signal(LocationEntry)

    def __init__(self, location: LocationEntry, parent=None):
        super().__init__(location.name, parent)
        self.location = location
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)
        # Larger font for touch readability.
        font = self.font()
        font.setPointSize(18)
        self.setFont(font)

        # Make the button visually suitable for touch input.
        self.setMinimumSize(200, 120)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_AcceptTouchEvents, True)
        self.setStyleSheet(
            "QPushButton {"
            " background-color: #f4f8ff;"
            " border: 2px solid #92a9d1;"
            " border-radius: 18px;"
            " padding: 12px;"
            "}"
            "QPushButton:pressed {"
            " background-color: #dbe7ff;"
            "}"
            "QPushButton:focus {"
            " border: 4px solid #2f5bd3;"
            " background-color: #e7efff;"
            "}"
        )

        # Connect left-click.
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self):
        """Handle normal (left) click: activate this location."""
        self.request_activate.emit(self.location)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """
        Right-click (or long-press mapped by OS) opens a context menu
        to rename or delete the location.
        """
        menu = QtWidgets.QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        action = menu.exec_(event.globalPos())
        if action == rename_action:
            self.request_rename.emit(self.location)
        elif action == delete_action:
            self.request_delete.emit(self.location)


class HmiMainWindow(QtWidgets.QMainWindow):
    """
    Main HMI window.

    Shows:
      - A grid of location buttons.
      - An "Add Location" button to create new entries.

    Later we can add status bars, camera/LiDAR indicators, etc.
    """

    def __init__(self, node: Node, model: LocationModel):
        super().__init__()
        self._node = node
        self._model = model
        self._admin_window = None
        self._location_buttons: list[LocationButton] = []
        self._focused_location_index = -1
        self._demo_input_mode = DEMO_INPUT_AUTO
        self._last_input_source = "Waiting for interaction"
        self._last_touch_timestamp = 0.0
        
        # Detect input devices (mouse, keyboard)
        self.input_detector = InputDeviceDetector()
        self.use_keyboard_mouse = self.input_detector.has_physical_input()

        self.setWindowTitle("Robot HMI - Location Selector")
        self.setAttribute(QtCore.Qt.WA_AcceptTouchEvents, True)
        # For a kiosk on the 27" screen you can use showFullScreen().
        self.showMaximized()
        self.statusBar().setSizeGripEnabled(False)

        central = QtWidgets.QWidget(self)
        central.setAttribute(QtCore.Qt.WA_AcceptTouchEvents, True)
        central.installEventFilter(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Animated eyes widget (robot "face") at the top of the screen.
        self.eyes_widget = EyesWidget(self)
        main_layout.addWidget(self.eyes_widget)

        # Top label / header (can later show robot state, etc.).
        header = QtWidgets.QLabel("Select Destination")
        header_font = header.font()
        header_font.setPointSize(24)
        header.setFont(header_font)
        header.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(header)

        info_frame = QtWidgets.QFrame(self)
        info_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        info_frame.setStyleSheet(
            "QFrame {"
            " background-color: #eef4ff;"
            " border: 1px solid #b6c8ea;"
            " border-radius: 14px;"
            "}"
        )
        info_layout = QtWidgets.QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(8)

        status_top_row = QtWidgets.QHBoxLayout()
        self.input_mode_label = QtWidgets.QLabel()
        self.detected_devices_label = QtWidgets.QLabel()
        status_top_row.addWidget(self.input_mode_label, 1)
        status_top_row.addWidget(self.detected_devices_label, 1)
        info_layout.addLayout(status_top_row)

        mode_row = QtWidgets.QHBoxLayout()
        mode_caption = QtWidgets.QLabel("Demo input profile:")
        mode_caption_font = mode_caption.font()
        mode_caption_font.setPointSize(12)
        mode_caption.setFont(mode_caption_font)
        mode_row.addWidget(mode_caption)

        self.demo_mode_combo = QtWidgets.QComboBox()
        self.demo_mode_combo.addItem("Auto detect", DEMO_INPUT_AUTO)
        self.demo_mode_combo.addItem("Touch demo", DEMO_INPUT_TOUCH)
        self.demo_mode_combo.addItem("Mouse demo", DEMO_INPUT_MOUSE)
        self.demo_mode_combo.addItem("Keyboard demo", DEMO_INPUT_KEYBOARD)
        self.demo_mode_combo.setMinimumHeight(44)
        demo_mode_font = self.demo_mode_combo.font()
        demo_mode_font.setPointSize(12)
        self.demo_mode_combo.setFont(demo_mode_font)
        self.demo_mode_combo.currentIndexChanged.connect(self.on_demo_mode_changed)
        mode_row.addWidget(self.demo_mode_combo)

        help_button = QtWidgets.QPushButton("Show shortcuts")
        help_button.setMinimumHeight(44)
        help_button.clicked.connect(self.show_shortcuts_dialog)
        mode_row.addWidget(help_button)
        info_layout.addLayout(mode_row)

        self.last_action_label = QtWidgets.QLabel()
        self.last_action_label.setWordWrap(True)
        info_layout.addWidget(self.last_action_label)

        self.keyboard_help_label = QtWidgets.QLabel()
        self.keyboard_help_label.setWordWrap(True)
        info_layout.addWidget(self.keyboard_help_label)

        main_layout.addWidget(info_frame)

        # Grid of location buttons.
        self.grid_widget = QtWidgets.QWidget()
        self.grid_widget.setAttribute(QtCore.Qt.WA_AcceptTouchEvents, True)
        self.grid_widget.installEventFilter(self)
        self.grid_layout = QtWidgets.QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(15)
        main_layout.addWidget(self.grid_widget, 1)

        # Bottom bar with (public) Add button and Admin menu.
        bottom_bar = QtWidgets.QHBoxLayout()

        add_button = QtWidgets.QPushButton("+ Add Destination")
        add_font = add_button.font()
        add_font.setPointSize(20)
        add_button.setFont(add_font)
        add_button.setMinimumHeight(80)
        add_button.setMinimumWidth(240)
        add_button.installEventFilter(self)
        add_button.clicked.connect(self.add_location_dialog)
        bottom_bar.addWidget(add_button)

        # Spacer then Admin button to open the admin window.
        bottom_bar.addStretch(1)

        admin_button = QtWidgets.QPushButton("Admin")
        admin_font = admin_button.font()
        admin_font.setPointSize(16)
        admin_button.setFont(admin_font)
        admin_button.setMinimumHeight(60)
        admin_button.setMinimumWidth(160)
        admin_button.installEventFilter(self)
        admin_button.clicked.connect(self.open_admin_window)
        bottom_bar.addWidget(admin_button)

        main_layout.addLayout(bottom_bar)

        # When model changes, rebuild the grid.
        self._model.locations_changed.connect(self.rebuild_grid)
        self.update_input_status()
        self.show_demo_feedback("Demo ready. Select a destination with touch, mouse, or keyboard.")
        self.rebuild_grid()

    # ------------------------------------------------------------------
    # Grid management
    # ------------------------------------------------------------------

    def clear_grid(self):
        """Remove all widgets from the grid layout."""
        self._location_buttons = []
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def rebuild_grid(self):
        """
        Rebuild the grid of location buttons based on the model contents.

        Grid layout strategy:
          - Fixed number of columns (e.g. 4).
          - Rows created as needed.
        """
        self.clear_grid()
        locations = self._model.locations

        # You can tweak columns for your screen (1920x1080).
        columns = 4
        for idx, loc in enumerate(locations):
            row = idx // columns
            col = idx % columns
            btn = LocationButton(loc, self.grid_widget)
            btn.installEventFilter(self)
            btn.request_rename.connect(self.rename_location_dialog)
            btn.request_delete.connect(self.delete_location_dialog)
            btn.request_activate.connect(self.activate_location)
            self._location_buttons.append(btn)
            self.grid_layout.addWidget(btn, row, col)

        if self._location_buttons:
            if self._focused_location_index < 0:
                self._focused_location_index = 0
            self.focus_location_button(min(self._focused_location_index, len(self._location_buttons) - 1))
        else:
            self._focused_location_index = -1

    # ------------------------------------------------------------------
    # Dialogs for add/rename/delete
    # ------------------------------------------------------------------

    def add_location_dialog(self):
        """Prompt user to enter a new location name."""
        text, ok = run_text_input_dialog(self, "Add Location", "Enter location name:")
        if not ok or not text.strip():
            return
        self._model.add_location(text.strip())
        self.show_demo_feedback(f"Added destination '{text.strip()}'.")

    def rename_location_dialog(self, loc: LocationEntry):
        """Prompt user to rename an existing location."""
        text, ok = run_text_input_dialog(self, "Rename Location", "New name:", default_text=loc.name)
        if not ok or not text.strip():
            return
        self._model.rename_location(loc, text.strip())
        self.show_demo_feedback(f"Renamed destination to '{text.strip()}'.")

    def delete_location_dialog(self, loc: LocationEntry):
        """Ask for confirmation, then delete the selected location."""
        reply = show_message_box(
            self,
            QtWidgets.QMessageBox.Warning,
            "Delete Location",
            f"Delete location '{loc.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._model.remove_location(loc)
            self.show_demo_feedback(f"Deleted destination '{loc.name}'.")

    # ------------------------------------------------------------------
    # Admin interface
    # ------------------------------------------------------------------

    def open_admin_window(self):
        """Open the admin window for managing destinations."""
        if self._admin_window is None:
            self._admin_window = AdminWindow(self._model, self)
        self._admin_window.show()
        self._admin_window.raise_()
        self._admin_window.activateWindow()
        self.show_demo_feedback("Admin window opened.")

    # ------------------------------------------------------------------
    # Activation (ROS integration point)
    # ------------------------------------------------------------------

    def activate_location(self, loc: LocationEntry):
        """
        Called when the operator taps a location button.

        For now, just log it; later we will publish a ROS message
        (e.g., goal, mission command) using self._node.
        """
        self._node.get_logger().info(f"Location selected: id={loc.id}, name={loc.name}")
        # Give the eyes a short happy reaction when a location is selected.
        if hasattr(self, "eyes_widget") and self.eyes_widget is not None:
            self.eyes_widget.set_mood(EyeMood.HAPPY)
            self.eyes_widget.blink()
        self.show_demo_feedback(
            f"Activated destination '{loc.name}' using {self.current_demo_input_label().lower()} input."
        )
        # TODO: Publish a ROS message here, e.g.:
        # msg = YourGoalMsg()
        # msg.location_id = loc.id
        # self._goal_pub.publish(msg)

    def call_shutdown_service(self):
        """Call the shutdown service on the SER8.
        
        Raises:
            Exception: if the service call fails or times out
        """
        from std_srvs.srv import Empty
        
        # Create a client for the shutdown service
        client = self._node.create_client(Empty, '/ser8/shutdown_system')
        
        # Wait for service to be available (with timeout)
        if not client.wait_for_service(timeout_sec=5.0):
            raise Exception("Shutdown service (/ser8/shutdown_system) not available")
        
        # Create request and call the service
        request = Empty.Request()
        future = client.call_async(request)
        
        # Wait for response with timeout
        timeout = time.time() + 10.0
        while not future.done():
            if time.time() > timeout:
                raise Exception("Shutdown service call timed out")
            time.sleep(0.1)
        
        # Check result
        result = future.result()
        self._node.get_logger().info("Shutdown service call succeeded")
        return result

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.TouchBegin:
            self._last_touch_timestamp = time.monotonic()
            self.update_last_input_source("Touch")
        elif event.type() == QtCore.QEvent.MouseButtonPress:
            if time.monotonic() - self._last_touch_timestamp > 0.7:
                self.update_last_input_source("Mouse")
        return super().eventFilter(watched, event)

    def current_demo_input_label(self) -> str:
        """Return the currently active demo input profile label."""
        mode = self._demo_input_mode
        if mode == DEMO_INPUT_TOUCH:
            return "Touch"
        if mode == DEMO_INPUT_MOUSE:
            return "Mouse"
        if mode == DEMO_INPUT_KEYBOARD:
            return "Keyboard"
        if self._last_input_source != "Waiting for interaction":
            return self._last_input_source
        if self.use_keyboard_mouse:
            return "Mouse/Keyboard"
        return "Touch"

    def update_input_status(self) -> None:
        """Refresh the demo status panel."""
        mode_descriptions = {
            DEMO_INPUT_AUTO: "Auto detect: live hardware detection",
            DEMO_INPUT_TOUCH: "Touch demo: show touch-oriented guidance",
            DEMO_INPUT_MOUSE: "Mouse demo: show pointer-oriented guidance",
            DEMO_INPUT_KEYBOARD: "Keyboard demo: show navigation shortcuts",
        }
        self.input_mode_label.setText(f"Active profile: {mode_descriptions[self._demo_input_mode]}")
        self.detected_devices_label.setText(
            f"Detected hardware: {self.input_detector.describe_detected_devices()}"
        )

        if self._demo_input_mode == DEMO_INPUT_KEYBOARD:
            self.keyboard_help_label.setText(
                "Keyboard demo: Arrow keys move between destinations, Enter activates, "
                "Ctrl+A adds a destination, / opens Admin, Esc closes Admin."
            )
        elif self._demo_input_mode == DEMO_INPUT_MOUSE:
            self.keyboard_help_label.setText(
                "Mouse demo: Left-click selects a destination, right-click a destination for quick rename/delete, "
                "and use Admin for full editing."
            )
        elif self._demo_input_mode == DEMO_INPUT_TOUCH:
            self.keyboard_help_label.setText(
                "Touch demo: Tap a destination to activate it, use the large Add Destination and Admin buttons, "
                "and complete changes through the oversized dialogs."
            )
        else:
            self.keyboard_help_label.setText(
                "Auto demo: The interface is configured for touch, mouse, and keyboard. "
                "Use Show shortcuts to review the keyboard path."
            )

    def update_last_input_source(self, source: str) -> None:
        """Track the most recent interaction source for the live demo."""
        self._last_input_source = source
        self.last_action_label.setText(f"Last input detected: {source}")

    def show_demo_feedback(self, message: str) -> None:
        """Show user-visible feedback for demonstration purposes."""
        self.last_action_label.setText(
            f"Last input detected: {self._last_input_source} | Last action: {message}"
        )
        self.statusBar().showMessage(message, 5000)

    def on_demo_mode_changed(self) -> None:
        """Apply the selected demo input profile."""
        self._demo_input_mode = self.demo_mode_combo.currentData()
        self.update_input_status()
        self.show_demo_feedback(
            f"Switched demo profile to {self.demo_mode_combo.currentText()}."
        )

    def show_shortcuts_dialog(self) -> None:
        """Display keyboard and pointer shortcuts for the demo operator."""
        shortcuts_text = (
            "Keyboard controls:\n"
            "  Arrow keys: move between destination buttons\n"
            "  Enter/Return: activate focused destination\n"
            "  Ctrl+A: add destination\n"
            "  / : open Admin\n"
            "  Admin window: Ctrl+N add, Ctrl+R rename, Ctrl+D delete, Ctrl+Up/Down reorder, Esc close\n\n"
            "Pointer and touch controls:\n"
            "  Tap or left-click: activate destination\n"
            "  Right-click: quick rename/delete context menu\n"
            "  Add Destination and Admin buttons are sized for touch use"
        )
        show_message_box(
            self,
            QtWidgets.QMessageBox.Information,
            "Demo Shortcuts",
            shortcuts_text,
            QtWidgets.QMessageBox.Ok,
            QtWidgets.QMessageBox.Ok,
        )

    def keyboard_controls_enabled(self) -> bool:
        """Return whether keyboard demo controls should be active."""
        return self.use_keyboard_mouse or self._demo_input_mode == DEMO_INPUT_KEYBOARD

    def focus_location_button(self, index: int) -> None:
        """Set keyboard focus to a specific location button."""
        if not self._location_buttons:
            self._focused_location_index = -1
            return
        self._focused_location_index = max(0, min(index, len(self._location_buttons) - 1))
        self._location_buttons[self._focused_location_index].setFocus()

    def move_focus_by(self, row_delta: int, column_delta: int) -> None:
        """Move focus across the location grid using keyboard navigation."""
        if not self._location_buttons:
            return

        columns = 4
        current = self._focused_location_index if self._focused_location_index >= 0 else 0
        row = current // columns
        column = current % columns
        new_index = (row + row_delta) * columns + (column + column_delta)
        new_index = max(0, min(new_index, len(self._location_buttons) - 1))
        self.focus_location_button(new_index)
        self.show_demo_feedback(
            f"Focused destination '{self._location_buttons[new_index].location.name}'."
        )

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle keyboard shortcuts when keyboard is detected."""
        if not self.keyboard_controls_enabled():
            super().keyPressEvent(event)
            return

        self.update_last_input_source("Keyboard")
        
        # Keyboard shortcuts
        if event.key() == QtCore.Qt.Key_Escape:
            # Escape key to close/exit (useful for kiosk)
            pass  # Ignore by default
        elif event.key() == QtCore.Qt.Key_Left:
            self.move_focus_by(0, -1)
        elif event.key() == QtCore.Qt.Key_Right:
            self.move_focus_by(0, 1)
        elif event.key() == QtCore.Qt.Key_Up:
            self.move_focus_by(-1, 0)
        elif event.key() == QtCore.Qt.Key_Down:
            self.move_focus_by(1, 0)
        elif event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if 0 <= self._focused_location_index < len(self._location_buttons):
                self.activate_location(self._location_buttons[self._focused_location_index].location)
        elif event.key() == QtCore.Qt.Key_A and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+A: Add location
            self.add_location_dialog()
        elif event.key() == QtCore.Qt.Key_Slash:
            # Forward slash: Open admin menu
            self.open_admin_window()
        else:
            super().keyPressEvent(event)


class HmiRosNode(Node):
    """
    ROS 2 node backing the HMI.

    At this stage it mainly provides logging and will later
    host publishers/subscribers for robot state, goals, etc.
    """

    def __init__(self):
        super().__init__("hmi_node")
        # Example: placeholder for a future goal publisher
        # from std_msgs.msg import String
        # self.goal_pub = self.create_publisher(String, "/hmi/selected_location", 10)


class AdminWindow(QtWidgets.QMainWindow):
    """Administrator-only window for managing destinations.

    This window provides a more guided flow for adding destinations and
    tools for renaming, deleting, and reordering the list.
    """

    def __init__(self, model: LocationModel, parent=None):
        super().__init__(parent)
        self._model = model
        
        # Inherit input device detection from parent if available
        self.use_keyboard_mouse = False
        if parent and hasattr(parent, 'use_keyboard_mouse'):
            self.use_keyboard_mouse = parent.use_keyboard_mouse

        self.setWindowTitle("Destination Administration")
        self.resize(900, 600)
        self.setAttribute(QtCore.Qt.WA_AcceptTouchEvents, True)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        title = QtWidgets.QLabel("Manage Destinations")
        title_font = title.font()
        title_font.setPointSize(20)
        title.setFont(title_font)
        title.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(title)

        # List of destinations.
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setSpacing(8)
        self.list_widget.setStyleSheet("QListWidget::item { min-height: 44px; }")
        list_font = self.list_widget.font()
        list_font.setPointSize(14)
        self.list_widget.setFont(list_font)
        main_layout.addWidget(self.list_widget, 1)

        # Toolbar / dropdown menu for actions (touch-friendly).
        toolbar_layout = QtWidgets.QHBoxLayout()

        # This combo acts as a simple "Edit" menu for the selected item.
        self.action_combo = QtWidgets.QComboBox()
        self.action_combo.addItem("Select action...")
        self.action_combo.addItem("Add new destination")
        self.action_combo.addItem("Rename destination")
        self.action_combo.addItem("Edit mapping")
        self.action_combo.addItem("Delete destination")
        self.action_combo.addItem("Move up")
        self.action_combo.addItem("Move down")
        self.action_combo.setMinimumHeight(50)
        toolbar_layout.addWidget(self.action_combo)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setMinimumHeight(50)
        apply_btn.clicked.connect(self.apply_selected_action)
        toolbar_layout.addWidget(apply_btn)

        # Eyes customization button.
        eyes_btn = QtWidgets.QPushButton("Eyes settings")
        eyes_btn.setMinimumHeight(50)
        eyes_btn.clicked.connect(self.open_eyes_settings)
        toolbar_layout.addWidget(eyes_btn)

        # Shutdown button.
        shutdown_btn = QtWidgets.QPushButton("Shutdown System")
        shutdown_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        shutdown_btn.setMinimumHeight(50)
        shutdown_btn.clicked.connect(self.on_shutdown_clicked)
        toolbar_layout.addWidget(shutdown_btn)

        toolbar_layout.addStretch(1)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setMinimumHeight(50)
        close_btn.clicked.connect(self.close)
        toolbar_layout.addWidget(close_btn)

        main_layout.addLayout(toolbar_layout)

        # React to model changes.
        self._model.locations_changed.connect(self.refresh_list)
        self.refresh_list()

    # ------------------------------------------------------------------
    # List helpers
    # ------------------------------------------------------------------

    def refresh_list(self):
        self.list_widget.clear()
        for idx, loc in enumerate(self._model.locations):
            item = QtWidgets.QListWidgetItem(f"{idx + 1}. {loc.name} (id={loc.id})")
            item.setData(QtCore.Qt.UserRole, loc.id)
            self.list_widget.addItem(item)
        if self._model.locations and self.list_widget.currentRow() < 0:
            self.list_widget.setCurrentRow(0)

    def current_index(self) -> int:
        row = self.list_widget.currentRow()
        return row

    def current_location(self) -> LocationEntry | None:
        row = self.current_index()
        if row < 0 or row >= len(self._model.locations):
            return None
        return self._model.locations[row]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def apply_selected_action(self):
        idx = self.action_combo.currentIndex()
        if idx == 1:
            self.add_destination_flow()
        elif idx == 2:
            self.rename_destination()
        elif idx == 3:
            self.edit_destination_mapping()
        elif idx == 4:
            self.delete_destination()
        elif idx == 5:
            self.move_destination_up()
        elif idx == 6:
            self.move_destination_down()

        # Reset to placeholder after action.
        self.action_combo.setCurrentIndex(0)

    def add_destination_flow(self):
        """Guided flow: name -> confirm -> mapping stub -> final confirm."""
        # Step 1: name with an on-screen keyboard (use normal input box for now).
        name, ok = run_text_input_dialog(self, "Add New Destination", "Enter destination name:")
        if not ok or not name.strip():
            return
        name = name.strip()

        # Step 2: confirm name.
        confirm = show_message_box(
            self,
            QtWidgets.QMessageBox.Question,
            "Confirm Name",
            f"Use destination name:\n\n{name}",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        # Step 3: mapping configuration placeholder.
        # For now we just ask whether to attach map/AprilTag info later.
        mapping_reply = show_message_box(
            self,
            QtWidgets.QMessageBox.Question,
            "Mapping Information",
            (
                "Mapping for this destination (floor plan / AprilTag) "
                "is not configured yet.\n\n"
                "Do you want to add it later?"
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if mapping_reply == QtWidgets.QMessageBox.No:
            # In a future version, this path would open a mapping editor.
            show_message_box(
                self,
                QtWidgets.QMessageBox.Information,
                "Mapping Editor",
                "Mapping editor is not implemented yet.",
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Ok,
            )

        # Step 4: final confirmation to add to database.
        final = show_message_box(
            self,
            QtWidgets.QMessageBox.Question,
            "Confirm Addition",
            f"Add '{name}' to the destination list?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if final != QtWidgets.QMessageBox.Yes:
            return

        self._model.add_location(name)
        # Ensure the newly added item is visible/selected.
        self.refresh_list()
        self.list_widget.setCurrentRow(len(self._model.locations) - 1)
        if isinstance(self.parent(), HmiMainWindow):
            self.parent().show_demo_feedback(f"Added destination '{name}' from Admin.")

    def rename_destination(self):
        loc = self.current_location()
        if loc is None:
            return
        new_name, ok = run_text_input_dialog(self, "Rename Destination", "New name:", default_text=loc.name)
        if not ok or not new_name.strip():
            return
        self._model.rename_location(loc, new_name.strip())
        if isinstance(self.parent(), HmiMainWindow):
            self.parent().show_demo_feedback(f"Renamed destination to '{new_name.strip()}' from Admin.")

    def delete_destination(self):
        loc = self.current_location()
        if loc is None:
            return
        reply = show_message_box(
            self,
            QtWidgets.QMessageBox.Warning,
            "Delete Destination",
            f"Delete destination '{loc.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._model.remove_location(loc)
            if isinstance(self.parent(), HmiMainWindow):
                self.parent().show_demo_feedback(f"Deleted destination '{loc.name}' from Admin.")

    def move_destination_up(self):
        row = self.current_index()
        if row <= 0:
            return
        self._model.move_location_up(row)
        self.refresh_list()
        self.list_widget.setCurrentRow(row - 1)
        if isinstance(self.parent(), HmiMainWindow):
            self.parent().show_demo_feedback("Moved destination up.")

    def move_destination_down(self):
        row = self.current_index()
        if row < 0 or row >= len(self._model.locations) - 1:
            return
        self._model.move_location_down(row)
        self.refresh_list()
        self.list_widget.setCurrentRow(row + 1)
        if isinstance(self.parent(), HmiMainWindow):
            self.parent().show_demo_feedback("Moved destination down.")

    def edit_destination_mapping(self):
        """Open a dialog to edit floor plan and AprilTag metadata."""
        loc = self.current_location()
        if loc is None:
            return

        dialog = MappingEditorDialog(loc, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            # The dialog modifies the LocationEntry in place; just save.
            self._model.save()
            self.refresh_list()
            if isinstance(self.parent(), HmiMainWindow):
                self.parent().show_demo_feedback(f"Updated mapping for '{loc.name}'.")

    def open_eyes_settings(self):
        """Open a dialog that lets admins customize the eyes widget."""
        # We expect the main window (parent) to provide an EyesWidget instance.
        main_window = self.parent()
        eyes = getattr(main_window, "eyes_widget", None)
        if eyes is None:
            show_message_box(
                self,
                QtWidgets.QMessageBox.Warning,
                "Eyes not available",
                "No eyes widget is available to configure.",
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Ok,
            )
            return

        dialog = EyesSettingsDialog(eyes, self)
        dialog.exec()

    def on_shutdown_clicked(self):
        """Handle shutdown button click with confirmation."""
        reply = show_message_box(
            self,
            QtWidgets.QMessageBox.Critical,
            "Confirm System Shutdown",
            "Are you sure you want to shutdown the entire robot system?\n\n",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        # Get the main window (parent)
        main_window = self.parent()
        if main_window is None:
            show_message_box(
                self,
                QtWidgets.QMessageBox.Warning,
                "Error",
                "Cannot access main window.",
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Ok,
            )
            return
        
        try:
            # Call the shutdown service via main window
            main_window.call_shutdown_service()
            
            show_message_box(
                self,
                QtWidgets.QMessageBox.Information,
                "Shutdown Initiated",
                "System shutdown has been initiated.\n\n"
                "The robot will shutdown gracefully.",
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Ok,
            )
            
            # Close the admin window after initiating shutdown
            self.close()
        except Exception as e:
            show_message_box(
                self,
                QtWidgets.QMessageBox.Critical,
                "Shutdown Error",
                f"Failed to initiate system shutdown:\n\n{str(e)}",
                QtWidgets.QMessageBox.Ok,
                QtWidgets.QMessageBox.Ok,
            )

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle keyboard shortcuts in admin window."""
        if not self.use_keyboard_mouse:
            super().keyPressEvent(event)
            return
        
        # Keyboard shortcuts for admin window
        if event.key() == QtCore.Qt.Key_Escape:
            # Escape key to close admin window
            self.close()
        elif event.key() == QtCore.Qt.Key_N and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+N: Add new destination
            self.add_destination_flow()
        elif event.key() == QtCore.Qt.Key_R and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+R: Rename destination
            self.rename_destination()
        elif event.key() == QtCore.Qt.Key_D and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+D: Delete destination
            self.delete_destination()
        elif event.key() == QtCore.Qt.Key_Up and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+Up: Move destination up
            self.move_destination_up()
        elif event.key() == QtCore.Qt.Key_Down and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+Down: Move destination down
            self.move_destination_down()
        elif event.key() == QtCore.Qt.Key_E and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+E: Eyes settings
            self.open_eyes_settings()
        elif event.key() == QtCore.Qt.Key_S and event.modifiers() & QtCore.Qt.ControlModifier:
            # Ctrl+S: Shutdown system
            self.on_shutdown_clicked()
        elif event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.apply_selected_action()
        else:
            super().keyPressEvent(event)


class MappingEditorDialog(QtWidgets.QDialog):
    """Dialog to edit mapping info (floor plan + AprilTags) for a location."""

    def __init__(self, location: LocationEntry, parent=None):
        super().__init__(parent)
        self._location = location

        self.setWindowTitle(f"Edit Mapping - {location.name}")
        self.resize(500, 300)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        info = QtWidgets.QLabel(
            "Configure the floor plan reference and AprilTag information for "
            "this destination."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()

        # Floor plan filename/reference.
        self.floor_plan_edit = QtWidgets.QLineEdit(self)
        if self._location.floor_plan:
            self.floor_plan_edit.setText(self._location.floor_plan)
        form.addRow("Floor plan file:", self.floor_plan_edit)

        # Primary AprilTag ID.
        self.tag_id_edit = QtWidgets.QLineEdit(self)
        if self._location.apriltag_id is not None:
            self.tag_id_edit.setText(str(self._location.apriltag_id))
        self.tag_id_edit.setPlaceholderText("Optional numeric tag ID, e.g. 23")
        form.addRow("AprilTag ID:", self.tag_id_edit)

        # Nearby AprilTag IDs as comma-separated list.
        self.nearby_tags_edit = QtWidgets.QLineEdit(self)
        if self._location.nearby_tags:
            self.nearby_tags_edit.setText(
                ",".join(str(t) for t in self._location.nearby_tags)
            )
        self.nearby_tags_edit.setPlaceholderText("Comma-separated IDs, e.g. 10,11,12")
        form.addRow("Nearby tag IDs:", self.nearby_tags_edit)

        layout.addLayout(form)

        # Buttons.
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self,
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        apply_touch_friendly_dialog(self)

    def accept(self) -> None:
        # Update floor plan reference.
        floor_plan = self.floor_plan_edit.text().strip()
        self._location.floor_plan = floor_plan or None

        # Update Apriltag ID.
        tag_text = self.tag_id_edit.text().strip()
        if tag_text:
            try:
                self._location.apriltag_id = int(tag_text)
            except ValueError:
                show_message_box(
                    self,
                    QtWidgets.QMessageBox.Warning,
                    "Invalid AprilTag ID",
                    "AprilTag ID must be an integer.",
                    QtWidgets.QMessageBox.Ok,
                    QtWidgets.QMessageBox.Ok,
                )
                return
        else:
            self._location.apriltag_id = None

        # Update nearby tag IDs.
        nearby_text = self.nearby_tags_edit.text().strip()
        if nearby_text:
            try:
                self._location.nearby_tags = [
                    int(part.strip())
                    for part in nearby_text.split(",")
                    if part.strip()
                ]
            except ValueError:
                show_message_box(
                    self,
                    QtWidgets.QMessageBox.Warning,
                    "Invalid Nearby Tags",
                    "Nearby tag IDs must be a comma-separated list of integers.",
                    QtWidgets.QMessageBox.Ok,
                    QtWidgets.QMessageBox.Ok,
                )
                return
        else:
            self._location.nearby_tags = None

        super().accept()


class EyesSettingsDialog(QtWidgets.QDialog):
    """Dialog for admin-side customization of the robot eyes widget."""

    def __init__(self, eyes_widget: EyesWidget, parent=None):
        super().__init__(parent)
        self._eyes = eyes_widget

        self.setWindowTitle("Eyes Settings")
        self.resize(400, 300)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        info = QtWidgets.QLabel(
            "Adjust visual settings for the robot's eyes."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtWidgets.QFormLayout()

        # Center pupil enabled.
        self.center_pupil_checkbox = QtWidgets.QCheckBox("Enable center pupil")
        # Approximate current value by checking if radius > 0 and enabled flag.
        self.center_pupil_checkbox.setChecked(self._eyes._config.center_pupil_enabled)
        self.center_pupil_checkbox.toggled.connect(self._on_center_pupil_toggled)
        form.addRow("Center pupil:", self.center_pupil_checkbox)

        # Center pupil size.
        self.center_pupil_size_spin = QtWidgets.QSpinBox()
        self.center_pupil_size_spin.setRange(2, 100)
        self.center_pupil_size_spin.setValue(self._eyes._config.center_pupil_radius)
        self.center_pupil_size_spin.valueChanged.connect(self._on_center_pupil_size_changed)
        form.addRow("Center pupil size:", self.center_pupil_size_spin)

        layout.addLayout(form)

        # Buttons.
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close,
            parent=self,
        )
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        # For a settings dialog, Close is enough; accept just closes as well.
        layout.addWidget(button_box)
        apply_touch_friendly_dialog(self)

        # Initialize enabled state based on checkbox.
        self._on_center_pupil_toggled(self.center_pupil_checkbox.isChecked())

    # Slots

    def _on_center_pupil_toggled(self, checked: bool) -> None:
        self._eyes.set_center_pupil_enabled(checked)
        self.center_pupil_size_spin.setEnabled(checked)

    def _on_center_pupil_size_changed(self, value: int) -> None:
        if self.center_pupil_checkbox.isChecked():
            self._eyes.set_center_pupil_radius(value)


def main():
    # Initialize ROS 2.
    rclpy.init()

    # Create the ROS node.
    node = HmiRosNode()

    # Determine a simple storage path for locations.json
    storage_path = os.path.join(os.path.dirname(__file__), "locations.json")
    model = LocationModel(storage_path)
    seeded_demo_data = model.ensure_demo_locations()
    if seeded_demo_data:
        node.get_logger().info("Seeded demo destinations in locations.json")

    # Integrate Qt event loop with ROS.
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_SynthesizeMouseForUnhandledTouchEvents,
        True,
    )
    app = QtWidgets.QApplication([])

    # Timer to periodically spin ROS so callbacks are processed.
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: rclpy.spin_once(node, timeout_sec=0.0))
    timer.start(10)  # 100 Hz polling; cheap since most loops do nothing.

    window = HmiMainWindow(node, model)
    window.show()

    exit_code = app.exec()

    # Clean shutdown.
    node.destroy_node()
    rclpy.shutdown()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()