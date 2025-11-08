# src/panels/data_management_panel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QGroupBox
from PySide6.QtCore import Signal, Slot
from typing import Optional


class DataManagementPanel(QWidget):
    # --- シグナル定義 ---
    saveClicked = Signal()
    exportClicked = Signal()
    importClicked = Signal()
    syncCsvClicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)  # ボタンを横に並べるので QHBoxLayout
        main_layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Data Management")
        layout = QHBoxLayout(group)  # グループ内部も横並び

        save_btn = QPushButton("💾 Save to DB")
        save_btn.clicked.connect(self.saveClicked)  # シグナル発行

        export_btn = QPushButton("📤 Export JSON")
        export_btn.clicked.connect(self.exportClicked)  # シグナル発行

        import_btn = QPushButton("📥 Import JSON")
        import_btn.clicked.connect(self.importClicked)  # シグナル発行

        sync_btn = QPushButton("🔄 Sync from CSV")
        sync_btn.clicked.connect(self.syncCsvClicked)

        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addWidget(import_btn)
        layout.addWidget(sync_btn)

        main_layout.addWidget(group)
