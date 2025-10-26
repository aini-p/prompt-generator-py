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


# ドラッグアンドドロップ可能なリストウィジェット (BatchPanelと同じものを使うか再定義)
class DraggableListWidget(QListWidget):
    # ... (BatchPanel と同じ実装) ...
    pass


class SequenceEditorDialog(QDialog):  # BaseEditorDialog を継承しない
    requestSceneSelection = Signal(object)  # シーン追加ボタンから MainWindow へ

    def __init__(
        self,
        initial_data: Optional[Sequence],
        db_data: Dict[str, Dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self.initial_data = initial_data
        self.db_data = db_data  # Scene データ参照用
        self.current_scene_entries: List[SequenceSceneEntry] = []
        if initial_data:
            self.setWindowTitle(f"Edit Sequence: {initial_data.name}")
            # Deep copy
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

        layout.addWidget(QLabel("Scenes:"))
        self.scene_list_widget = DraggableListWidget()
        # scene_list_widget の設定 (D&D, チェックボックス表示など)
        self.scene_list_widget.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )

        layout.addWidget(self.scene_list_widget)

        btn_layout = QHBoxLayout()
        add_scene_btn = QPushButton("＋ Add Scene")
        remove_scene_btn = QPushButton("－ Remove Scene")
        add_scene_btn.clicked.connect(self._request_scene_selection)
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
        self.scene_list_widget.clear()
        all_scenes = self.db_data.get("scenes", {})
        for entry in self.current_scene_entries:
            scene = all_scenes.get(entry.scene_id)
            if scene:
                item = QListWidgetItem(f"{scene.name} ({scene.id})")
                item.setData(Qt.ItemDataRole.UserRole, entry.scene_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if entry.is_enabled
                    else Qt.CheckState.Unchecked
                )
                self.scene_list_widget.addItem(item)
            else:
                # 存在しないシーンIDが含まれている場合の処理 (無視するか表示するか)
                print(f"[WARN] Scene ID {entry.scene_id} not found in database.")

    @Slot()
    def _request_scene_selection(self):
        # MainWindow にシーン選択ダイアログの表示を依頼する (複数選択可能なリストなど)
        # ここでは単純化のため、シグナルだけ送る
        self.requestSceneSelection.emit(
            self
        )  # 自分自身を渡して、結果をコールバックしてもらう想定

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
