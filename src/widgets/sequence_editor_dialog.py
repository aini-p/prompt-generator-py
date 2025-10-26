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
)
from PySide6.QtCore import Qt, Slot, Signal
from typing import Optional, Dict, List, Any

from .base_editor_dialog import BaseEditorDialog  # 継承しない独立ダイアログでも可
from ..models import Scene, Sequence, SequenceSceneEntry
from .scene_selection_dialog import SceneSelectionDialog


# ドラッグアンドドロップ可能なリストウィジェット (BatchPanelと同じものを使うか再定義)
class DraggableListWidget(QListWidget):
    # ... (BatchPanel と同じ実装) ...
    pass


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
        remove_scene_btn = QPushButton("－ Remove Selected Scene")  # ボタンテキスト変更
        # ▼▼▼ _request_scene_selection -> _open_scene_selection_dialog に変更 ▼▼▼
        add_scene_btn.clicked.connect(self._open_scene_selection_dialog)
        # ▲▲▲ 変更ここまで ▲▲▲
        remove_scene_btn.clicked.connect(self._remove_selected_scene)
        btn_layout.addWidget(add_scene_btn)
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
            item_text = (
                f"Scene ID not found: {entry.scene_id}"  # 見つからない場合の表示
            )
            if scene:
                item_text = f"{getattr(scene, 'name', 'Unnamed')} ({entry.scene_id})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entry.scene_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if entry.is_enabled else Qt.CheckState.Unchecked
            )
            self.scene_list_widget.addItem(item)

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

    def get_data(self) -> Optional[Sequence]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Name is required.")
            return None

        # UIのリスト順序とチェック状態から current_scene_entries を更新
        new_entries: List[SequenceSceneEntry] = []
        all_scenes = self.db_data.get("scenes", {})
        for i in range(self.scene_list_widget.count()):
            item = self.scene_list_widget.item(i)
            scene_id = item.data(Qt.ItemDataRole.UserRole)
            if scene_id in all_scenes:  # 存在確認
                is_enabled = item.checkState() == Qt.CheckState.Checked
                new_entries.append(
                    SequenceSceneEntry(scene_id=scene_id, is_enabled=is_enabled)
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
