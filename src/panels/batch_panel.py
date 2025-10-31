# src/panels/batch_panel.py
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QGroupBox,
    QListWidgetItem,
    QLabel,
    QProgressBar,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, Slot, QModelIndex, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent
from typing import List, Optional, Dict, Any

from ..models import Sequence, QueueItem


# ドラッグアンドドロップ可能なリストウィジェット
class DraggableListWidget(QListWidget):
    itemsReordered = Signal(list)  # 新しい順序のIDリストを発行

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event: QDropEvent):
        super().dropEvent(event)
        # ドロップ後に新しい順序のIDリストを取得してシグナルを発行
        new_order_ids = [
            self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())
        ]
        self.itemsReordered.emit(new_order_ids)


class BatchPanel(QWidget):
    # シグナル定義
    addSequenceClicked = Signal()
    editSequenceClicked = Signal(str)  # sequence_id
    deleteSequenceClicked = Signal(str)  # sequence_id
    addSequenceToQueueClicked = Signal(str)  # sequence_id
    editQueueItemAssignmentsClicked = Signal(str)  # queue_item_id
    removeQueueItemClicked = Signal(str)  # queue_item_id
    clearQueueClicked = Signal()
    runBatchClicked = Signal()
    sequencesReordered = Signal(list)  # new sequence ids order
    queueItemsReordered = Signal(list)  # new queue item ids order

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._sequences_ref: Dict[str, Sequence] = {}
        self._queue_ref: List[QueueItem] = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- シーケンス管理 ---
        sequence_group = QGroupBox("Sequences")
        sequence_layout = QVBoxLayout(sequence_group)
        self.sequence_list = DraggableListWidget()
        self.sequence_list.itemDoubleClicked.connect(self._on_sequence_double_clicked)
        self.sequence_list.itemsReordered.connect(
            self.sequencesReordered
        )  # D&D シグナル
        sequence_layout.addWidget(self.sequence_list)
        seq_btn_layout = QHBoxLayout()
        add_seq_btn = QPushButton("＋ Add Sequence")
        edit_seq_btn = QPushButton("✎ Edit Sequence")
        del_seq_btn = QPushButton("🗑️ Delete Sequence")
        add_to_queue_btn = QPushButton("➡️ Add to Queue")
        add_seq_btn.clicked.connect(self.addSequenceClicked)
        edit_seq_btn.clicked.connect(self._emit_edit_sequence)
        del_seq_btn.clicked.connect(self._emit_delete_sequence)
        add_to_queue_btn.clicked.connect(self._emit_add_to_queue)
        seq_btn_layout.addWidget(add_seq_btn)
        seq_btn_layout.addWidget(edit_seq_btn)
        seq_btn_layout.addWidget(del_seq_btn)
        seq_btn_layout.addStretch()
        seq_btn_layout.addWidget(add_to_queue_btn)
        sequence_layout.addLayout(seq_btn_layout)
        main_layout.addWidget(sequence_group)

        # --- バッチキュー管理 ---
        queue_group = QGroupBox("Batch Queue")
        queue_layout = QVBoxLayout(queue_group)
        self.queue_list = DraggableListWidget()
        self.queue_list.itemsReordered.connect(self.queueItemsReordered)  # D&D シグナル
        queue_layout.addWidget(self.queue_list)
        queue_btn_layout = QHBoxLayout()
        edit_assign_btn = QPushButton("✎ Edit Assignments")
        remove_queue_btn = QPushButton("🗑️ Remove from Queue")
        clear_queue_btn = QPushButton("🧹 Clear Queue")
        edit_assign_btn.clicked.connect(self._emit_edit_assignments)
        remove_queue_btn.clicked.connect(self._emit_remove_from_queue)
        clear_queue_btn.clicked.connect(self.clearQueueClicked)
        queue_btn_layout.addWidget(edit_assign_btn)
        queue_btn_layout.addWidget(remove_queue_btn)
        queue_btn_layout.addStretch()
        queue_btn_layout.addWidget(clear_queue_btn)
        queue_layout.addLayout(queue_btn_layout)
        main_layout.addWidget(queue_group)

        # --- 実行コントロール ---
        exec_group = QGroupBox("Execution")
        exec_layout = QVBoxLayout(exec_group)
        self.run_batch_btn = QPushButton("🚀 Run Batch")
        self.run_batch_btn.clicked.connect(self.runBatchClicked)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Status: Idle")  # 実行状況表示用
        exec_layout.addWidget(self.run_batch_btn)
        exec_layout.addWidget(self.progress_bar)
        exec_layout.addWidget(self.status_label)
        main_layout.addWidget(exec_group)

        main_layout.addStretch()

    def set_data_reference(
        self, sequences_data: Dict[str, Sequence], queue_data: List[QueueItem]
    ):
        self._sequences_ref = sequences_data
        self._queue_ref = queue_data
        self.update_sequence_list()
        self.update_queue_list()

    def update_sequence_list(self):
        self.sequence_list.blockSignals(True)
        self.sequence_list.clear()
        # ToDo: シーケンスをリストに追加 (名前とIDを表示、IDをUserRoleにセット)
        # ToDo: ドラッグアンドドロップ後の順序を反映させるには、
        #       MainWindow側で sequences データ自体を並び替えるか、
        #       表示順序用のデータを別に持つ必要がある。
        #       ここでは表示のみ更新する。
        # sorted_sequences = sorted(self._sequences_ref.values(), key=lambda s: s.name) # 名前順
        sorted_sequences = list(self._sequences_ref.values())  # DBからの読み込み順 (仮)
        for seq in sorted_sequences:
            item = QListWidgetItem(f"{seq.name} ({seq.id})")
            item.setData(Qt.ItemDataRole.UserRole, seq.id)
            self.sequence_list.addItem(item)
        self.sequence_list.blockSignals(False)

    def update_queue_list(self):
        self.queue_list.blockSignals(True)
        self.queue_list.clear()
        # order 順に並んでいるはず
        for item_data in self._queue_ref:
            seq_name = self._sequences_ref.get(
                item_data.sequence_id, Sequence(id="", name="Unknown Sequence")
            ).name
            # ToDo: アクター割り当て状況も表示すると親切かも
            list_item = QListWidgetItem(
                f"{item_data.order + 1}: {seq_name} ({item_data.sequence_id})"
            )
            list_item.setData(
                Qt.ItemDataRole.UserRole, item_data.id
            )  # UserRoleには QueueItem の ID をセット
            self.queue_list.addItem(list_item)
        self.queue_list.blockSignals(False)

    def set_status(self, text: str, progress: Optional[int] = None):
        self.status_label.setText(f"Status: {text}")
        if progress is not None:
            self.progress_bar.setValue(progress)
        # 実行完了時以外は 0 にリセットしない (ワーカーが細かい粒度で更新するため)
        if progress == 100 or progress == 0:
            self.progress_bar.setValue(progress)

    @Slot(str)
    def set_status_text(self, text: str):
        """ワーカーからの生ログを受け取り、ステータスラベルに表示する"""
        # 特定のキーワードが含まれていない限り、Status: を上書きしない
        # (GenImage.py が "Status:" という単語を出力しない前提)
        if "Status:" not in text:
            self.status_label.setText(text)
        # コンソールには常に出力
        # print(f"[Panel Log] {text}") # MainWindow 側で print しているので不要かも

    def set_buttons_enabled(self, enabled: bool):
        # 実行中にボタンを無効化するなどの制御用
        self.run_batch_btn.setEnabled(enabled)
        # 他のボタンも必要に応じて制御
        # (例: enabled でない間は他のボタンも無効にする)
        self.sequence_list.setEnabled(enabled)
        self.queue_list.setEnabled(enabled)
        # ... (add_seq_btn や edit_assign_btn なども無効化) ...
        for button in self.findChildren(QPushButton):
            if button != self.run_batch_btn:  # 実行ボタン自体以外
                button.setEnabled(enabled)

    # --- シグナル発行用スロット ---
    @Slot(QListWidgetItem)
    def _on_sequence_double_clicked(self, item: QListWidgetItem):
        if item:
            self.editSequenceClicked.emit(item.data(Qt.ItemDataRole.UserRole))

    @Slot()
    def _emit_edit_sequence(self):
        item = self.sequence_list.currentItem()
        if item:
            self.editSequenceClicked.emit(item.data(Qt.ItemDataRole.UserRole))

    @Slot()
    def _emit_delete_sequence(self):
        item = self.sequence_list.currentItem()
        if item:
            self.deleteSequenceClicked.emit(item.data(Qt.ItemDataRole.UserRole))

    @Slot()
    def _emit_add_to_queue(self):
        item = self.sequence_list.currentItem()
        if item:
            self.addSequenceToQueueClicked.emit(item.data(Qt.ItemDataRole.UserRole))

    @Slot()
    def _emit_edit_assignments(self):
        item = self.queue_list.currentItem()
        if item:
            self.editQueueItemAssignmentsClicked.emit(
                item.data(Qt.ItemDataRole.UserRole)
            )

    @Slot()
    def _emit_remove_from_queue(self):
        item = self.queue_list.currentItem()
        if item:
            self.removeQueueItemClicked.emit(item.data(Qt.ItemDataRole.UserRole))
