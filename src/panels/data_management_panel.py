# src/panels/data_management_panel.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QGroupBox
from PySide6.QtCore import Signal, Slot
from typing import Optional


class DataManagementPanel(QWidget):
    # --- シグナル定義 ---
    startBackendClicked = Signal()
    saveClicked = Signal()
    exportClicked = Signal()
    importClicked = Signal()
    syncCsvClicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Data Management")
        layout = QHBoxLayout(group)

        start_backend_btn = QPushButton("🚀 Start Backend")
        start_backend_btn.setToolTip("Starts the Forge and Dispatcher backend processes in a new console.")
        start_backend_btn.setStyleSheet("background-color: #007bff; color: white;")
        start_backend_btn.clicked.connect(self.startBackendClicked)

        save_btn = QPushButton("💾 Save to DB")
        save_btn.clicked.connect(self.saveClicked)

        export_btn = QPushButton("📤 Export JSON")
        export_btn.clicked.connect(self.exportClicked)

        import_btn = QPushButton("📥 Import JSON")
        import_btn.clicked.connect(self.importClicked)

        sync_btn = QPushButton("🔄 Sync from CSV")
        sync_btn.clicked.connect(self.syncCsvClicked)

        layout.addWidget(start_backend_btn)
        layout.addStretch()
        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addWidget(import_btn)
        layout.addWidget(sync_btn)

        main_layout.addWidget(group)
