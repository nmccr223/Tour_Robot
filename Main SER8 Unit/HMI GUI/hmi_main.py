import json
import os
from dataclasses import dataclass, asdict
from typing import List

import rclpy
from rclpy.node import Node

from PySide6 import QtCore, QtGui, QtWidgets

from eyes_widget import EyesWidget, EyeMood


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

    def add_location(self, name: str) -> None:
        """Add a new location with a generated ID."""
        # Simple ID: sequential number as string.
        next_id = str(len(self._locations) + 1)
        self._locations.append(LocationEntry(id=next_id, name=name))
        self.save()
        self.locations_changed.emit()

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

        self.setWindowTitle("Robot HMI - Location Selector")
        # For a kiosk on the 27" screen you can use showFullScreen().
        self.showMaximized()

        central = QtWidgets.QWidget(self)
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

        # Grid of location buttons.
        self.grid_widget = QtWidgets.QWidget()
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
        add_button.clicked.connect(self.add_location_dialog)
        bottom_bar.addWidget(add_button)

        # Spacer then Admin button to open the admin window.
        bottom_bar.addStretch(1)

        admin_button = QtWidgets.QPushButton("Admin")
        admin_font = admin_button.font()
        admin_font.setPointSize(16)
        admin_button.setFont(admin_font)
        admin_button.setMinimumHeight(60)
        admin_button.clicked.connect(self.open_admin_window)
        bottom_bar.addWidget(admin_button)

        main_layout.addLayout(bottom_bar)

        # When model changes, rebuild the grid.
        self._model.locations_changed.connect(self.rebuild_grid)
        self.rebuild_grid()

    # ------------------------------------------------------------------
    # Grid management
    # ------------------------------------------------------------------

    def clear_grid(self):
        """Remove all widgets from the grid layout."""
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
            btn.request_rename.connect(self.rename_location_dialog)
            btn.request_delete.connect(self.delete_location_dialog)
            btn.request_activate.connect(self.activate_location)
            self.grid_layout.addWidget(btn, row, col)

    # ------------------------------------------------------------------
    # Dialogs for add/rename/delete
    # ------------------------------------------------------------------

    def add_location_dialog(self):
        """Prompt user to enter a new location name."""
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Location",
            "Enter location name:",
        )
        if not ok or not text.strip():
            return
        self._model.add_location(text.strip())

    def rename_location_dialog(self, loc: LocationEntry):
        """Prompt user to rename an existing location."""
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Location",
            "New name:",
            text=loc.name,
        )
        if not ok or not text.strip():
            return
        self._model.rename_location(loc, text.strip())

    def delete_location_dialog(self, loc: LocationEntry):
        """Ask for confirmation, then delete the selected location."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Location",
            f"Delete location '{loc.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._model.remove_location(loc)

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
        # TODO: Publish a ROS message here, e.g.:
        # msg = YourGoalMsg()
        # msg.location_id = loc.id
        # self._goal_pub.publish(msg)


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

        self.setWindowTitle("Destination Administration")
        self.resize(900, 600)

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
        toolbar_layout.addWidget(self.action_combo)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_selected_action)
        toolbar_layout.addWidget(apply_btn)

        # Eyes customization button.
        eyes_btn = QtWidgets.QPushButton("Eyes settings")
        eyes_btn.clicked.connect(self.open_eyes_settings)
        toolbar_layout.addWidget(eyes_btn)

        toolbar_layout.addStretch(1)

        close_btn = QtWidgets.QPushButton("Close")
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
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add New Destination",
            "Enter destination name:",
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        # Step 2: confirm name.
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Name",
            f"Use destination name:\n\n{name}",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        # Step 3: mapping configuration placeholder.
        # For now we just ask whether to attach map/AprilTag info later.
        mapping_reply = QtWidgets.QMessageBox.question(
            self,
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
            QtWidgets.QMessageBox.information(
                self,
                "Mapping Editor",
                "Mapping editor is not implemented yet.",
            )

        # Step 4: final confirmation to add to database.
        final = QtWidgets.QMessageBox.question(
            self,
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

    def rename_destination(self):
        loc = self.current_location()
        if loc is None:
            return
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Destination",
            "New name:",
            text=loc.name,
        )
        if not ok or not new_name.strip():
            return
        self._model.rename_location(loc, new_name.strip())

    def delete_destination(self):
        loc = self.current_location()
        if loc is None:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Destination",
            f"Delete destination '{loc.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._model.remove_location(loc)

    def move_destination_up(self):
        row = self.current_index()
        if row <= 0:
            return
        self._model.move_location_up(row)
        self.refresh_list()
        self.list_widget.setCurrentRow(row - 1)

    def move_destination_down(self):
        row = self.current_index()
        if row < 0 or row >= len(self._model.locations) - 1:
            return
        self._model.move_location_down(row)
        self.refresh_list()
        self.list_widget.setCurrentRow(row + 1)

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

    def open_eyes_settings(self):
        """Open a dialog that lets admins customize the eyes widget."""
        # We expect the main window (parent) to provide an EyesWidget instance.
        main_window = self.parent()
        eyes = getattr(main_window, "eyes_widget", None)
        if eyes is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Eyes not available",
                "No eyes widget is available to configure.",
            )
            return

        dialog = EyesSettingsDialog(eyes, self)
        dialog.exec()


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
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid AprilTag ID",
                    "AprilTag ID must be an integer.",
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
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Nearby Tags",
                    "Nearby tag IDs must be a comma-separated list of integers.",
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

    # Integrate Qt event loop with ROS.
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