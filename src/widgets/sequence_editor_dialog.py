# src/widgets/sequence_editor_dialog.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QCheckBox,
    QDialogButtonBox,
    QMessageBox,
    QAbstractItemView,
    QFormLayout,
    QFileDialog,
)
from PySide6.QtCore import Qt, Slot, Signal
from typing import Optional, Dict, List, Any, Tuple

from ..models import Scene, Sequence, SequenceSceneEntry
from .scene_selection_dialog import SceneSelectionDialog


STATUS_LABELS = {
    "not_started": "未着手",
    "needs_adjustment": "要調整",
    "completed": "完成",
}


# ドラッグアンドドロップ可能なリストウィジェット (BatchPanelと同じものを使うか再定義)
class DraggableListWidget(QListWidget):
    # ... (BatchPanel と同じ実装) ...
    pass


class ScenePlanSettingsDialog(QDialog):
    def __init__(self, scene_name: str, entry: SequenceSceneEntry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scene Planning Settings")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.scene_name_label = QLabel(scene_name)
        form_layout.addRow("Scene:", self.scene_name_label)

        self.generated_check = QCheckBox("生成済み")
        progress_status = getattr(entry, "progress_status", "not_started") or "not_started"
        self.generated_check.setChecked(
            progress_status == "completed" or getattr(entry, "is_generated", False)
        )
        form_layout.addRow("Status:", self.generated_check)

        thumb_layout = QHBoxLayout()
        self.thumbnail_edit = QLineEdit(getattr(entry, "thumbnail_path", ""))
        self.thumbnail_edit.setPlaceholderText("サムネイル画像のパス")
        browse_btn = QPushButton("参照...")
        clear_btn = QPushButton("クリア")
        browse_btn.clicked.connect(self._browse_thumbnail)
        clear_btn.clicked.connect(lambda: self.thumbnail_edit.setText(""))
        thumb_layout.addWidget(self.thumbnail_edit)
        thumb_layout.addWidget(browse_btn)
        thumb_layout.addWidget(clear_btn)
        form_layout.addRow("Thumbnail:", thumb_layout)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @Slot()
    def _browse_thumbnail(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Thumbnail Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if file_path:
            self.thumbnail_edit.setText(file_path)

    def get_values(self) -> Tuple[bool, str]:
        return self.generated_check.isChecked(), self.thumbnail_edit.text().strip()


class SequenceEditorDialog(QDialog):
    # requestSceneSelection シグナルは不要になったので削除
    # requestSceneSelection = Signal(object)

    def __init__(
        self,
        initial_data: Optional[Sequence],
        db_data: Dict[str, Dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self.initial_data = initial_data
        self.db_data = db_data
        self.current_scene_entries: List[SequenceSceneEntry] = []
        if initial_data:
            self.setWindowTitle(f"Edit Sequence: {initial_data.name}")
            self.current_scene_entries = [
                SequenceSceneEntry(**entry.__dict__)
                for entry in initial_data.scene_entries
            ]
        else:
            self.setWindowTitle("Add New Sequence")

        self._init_ui()
        self._populate_scene_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", "New Sequence"))
        form_layout.addRow("Name:", self.name_edit)
        layout.addLayout(form_layout)

        layout.addWidget(QLabel("Scenes in Sequence (Drag to reorder):"))  # ラベル変更
        self.scene_list_widget = DraggableListWidget()
        self.scene_list_widget.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        layout.addWidget(self.scene_list_widget)

        btn_layout = QHBoxLayout()
        add_scene_btn = QPushButton("＋ Add Scene...")  # ボタンテキスト変更
        edit_plan_btn = QPushButton("✎ Scene Plan Settings...")
        remove_scene_btn = QPushButton("－ Remove Selected Scene")  # ボタンテキスト変更
        # ▼▼▼ _request_scene_selection -> _open_scene_selection_dialog に変更 ▼▼▼
        add_scene_btn.clicked.connect(self._open_scene_selection_dialog)
        edit_plan_btn.clicked.connect(self._edit_selected_scene_plan)
        # ▲▲▲ 変更ここまで ▲▲▲
        remove_scene_btn.clicked.connect(self._remove_selected_scene)
        btn_layout.addWidget(add_scene_btn)
        btn_layout.addWidget(edit_plan_btn)
        btn_layout.addWidget(remove_scene_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_scene_list(self):
        # (このメソッドは変更なし)
        self.scene_list_widget.clear()
        all_scenes = self.db_data.get("scenes", {})
        for entry in self.current_scene_entries:
            scene = all_scenes.get(entry.scene_id)
            item = QListWidgetItem(self._format_scene_item_text(entry, scene))
            item.setData(Qt.ItemDataRole.UserRole, entry.scene_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if entry.is_enabled else Qt.CheckState.Unchecked
            )
            if getattr(entry, "thumbnail_path", ""):
                item.setToolTip(getattr(entry, "thumbnail_path", ""))
            self.scene_list_widget.addItem(item)

    def _get_scene_entry_by_id(self, scene_id: str) -> Optional[SequenceSceneEntry]:
        for entry in self.current_scene_entries:
            if entry.scene_id == scene_id:
                return entry
        return None

    def _format_scene_item_text(
        self, entry: SequenceSceneEntry, scene: Optional[Scene]
    ) -> str:
        if not scene:
            return "Unknown Scene"

        display_name = getattr(scene, "name", "Unnamed")
        status_tokens = []
                progress_status = getattr(entry, "progress_status", "not_started") or "not_started"
                if progress_status in STATUS_LABELS:
                    status_tokens.append(STATUS_LABELS[progress_status])
                elif getattr(entry, "is_generated", False):
                    status_tokens.append("完成")
        if getattr(entry, "thumbnail_path", ""):
            status_tokens.append("サムネあり")
        status_suffix = f" [{' / '.join(status_tokens)}]" if status_tokens else ""
        return f"{display_name}{status_suffix}"

    @Slot()
    def _open_scene_selection_dialog(self):
        """シーン選択ダイアログを開き、選択されたシーンを追加します。"""
        all_scenes = self.db_data.get("scenes", {})
        if not all_scenes:
            QMessageBox.information(
                self, "Add Scene", "No scenes available in the database."
            )
            return

        dialog = SceneSelectionDialog(all_scenes, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_id = dialog.get_selected_scene_id()
            if selected_id:
                # add_selected_scenes はリストを受け取る想定なのでリストで渡す
                self.add_selected_scenes([selected_id])

    # MainWindow からシーンが選択された後に呼ばれる想定のメソッド
    def add_selected_scenes(self, scene_ids: List[str]):
        added = False
        existing_ids = {entry.scene_id for entry in self.current_scene_entries}
        for scene_id in scene_ids:
            if scene_id not in existing_ids:
                # order はリストの末尾に追加されることで決まる
                self.current_scene_entries.append(
                    SequenceSceneEntry(scene_id=scene_id, is_enabled=True)
                )
                added = True
        if added:
            self._populate_scene_list()

    @Slot()
    def _remove_selected_scene(self):
        selected_items = self.scene_list_widget.selectedItems()
        if not selected_items:
            return

        selected_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        # current_scene_entries から削除
        self.current_scene_entries = [
            entry
            for entry in self.current_scene_entries
            if entry.scene_id != selected_id
        ]
        # UIから削除
        self.scene_list_widget.takeItem(self.scene_list_widget.row(selected_items[0]))

    @Slot()
    def _edit_selected_scene_plan(self):
        selected_items = self.scene_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Scene Plan", "シーンを選択してください。")
            return

        selected_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        entry = self._get_scene_entry_by_id(selected_id)
        if not entry:
            return

        scene = self.db_data.get("scenes", {}).get(selected_id)
        scene_name = getattr(scene, "name", "Unknown Scene")
        dialog = ScenePlanSettingsDialog(scene_name, entry, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            is_generated, thumbnail_path = dialog.get_values()
            entry.is_generated = is_generated
            entry.progress_status = "completed" if is_generated else "not_started"
            entry.thumbnail_path = thumbnail_path

            selected_item = selected_items[0]
            selected_item.setText(self._format_scene_item_text(entry, scene))
            selected_item.setToolTip(entry.thumbnail_path if entry.thumbnail_path else "")

    def get_data(self) -> Optional[Sequence]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Name is required.")
            return None

        # UIのリスト順序とチェック状態から current_scene_entries を更新
        new_entries: List[SequenceSceneEntry] = []
        all_scenes = self.db_data.get("scenes", {})
        existing_entry_map = {
            entry.scene_id: entry for entry in self.current_scene_entries
        }
        for i in range(self.scene_list_widget.count()):
            item = self.scene_list_widget.item(i)
            scene_id = item.data(Qt.ItemDataRole.UserRole)
            if scene_id in all_scenes:  # 存在確認
                is_enabled = item.checkState() == Qt.CheckState.Checked
                original_entry = existing_entry_map.get(scene_id, SequenceSceneEntry(scene_id=scene_id))
                new_entries.append(
                    SequenceSceneEntry(
                        scene_id=scene_id,
                        is_enabled=is_enabled,
                        scene_title=getattr(original_entry, "scene_title", ""),
                        notes=getattr(original_entry, "notes", ""),
                        is_generated=getattr(original_entry, "is_generated", False),
                        progress_status=getattr(
                            original_entry,
                            "progress_status",
                            "completed" if getattr(original_entry, "is_generated", False) else "not_started",
                        ),
                        thumbnail_path=getattr(original_entry, "thumbnail_path", ""),
                    )
                )

        if self.initial_data:  # 更新
            self.initial_data.name = name
            self.initial_data.scene_entries = new_entries
            return self.initial_data
        else:  # 新規
            return Sequence(
                id=f"seq_{int(time.time() * 1000)}",
                name=name,
                scene_entries=new_entries,
            )

    def accept(self):
        """Save a new sequence and update the list of sequences."""
        data = self.get_data()
        if data:
            self.saved_data = data
            super().accept()
