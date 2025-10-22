# src/widgets/add_direction_form.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any
from ..models import Direction, FullDatabase


class AddDirectionForm(QDialog):
    def __init__(
        self, initial_data: Optional[Direction], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            "演出 (Direction) の編集"
            if initial_data
            else "新規 演出 (Direction) の追加"
        )
        self.db_dict = db_dict
        self.initial_data = initial_data
        self.saved_data: Optional[Direction] = None

        # UI Elements
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.prompt_edit = QTextEdit()
        self.negative_prompt_edit = QTextEdit()
        self.costume_combo = QComboBox()
        self.pose_combo = QComboBox()
        self.expression_combo = QComboBox()

        # Populate Combos
        self.costume_items = [("", "(上書きしない)")] + [
            (cid, c.name) for cid, c in self.db_dict.get("costumes", {}).items()
        ]
        self.pose_items = [("", "(上書きしない)")] + [
            (pid, p.name) for pid, p in self.db_dict.get("poses", {}).items()
        ]
        self.expression_items = [("", "(上書きしない)")] + [
            (eid, e.name) for eid, e in self.db_dict.get("expressions", {}).items()
        ]

        self.costume_combo.addItems([name for _, name in self.costume_items])
        self.pose_combo.addItems([name for _, name in self.pose_items])
        self.expression_combo.addItems([name for _, name in self.expression_items])

        # Set Initial Data
        if initial_data:
            self.name_edit.setText(initial_data.name)
            self.tags_edit.setText(", ".join(initial_data.tags))
            self.prompt_edit.setPlainText(initial_data.prompt)
            self.negative_prompt_edit.setPlainText(initial_data.negative_prompt)
            # Set combo selection based on ID
            try:
                self.costume_combo.setCurrentIndex(
                    [cid for cid, _ in self.costume_items].index(
                        initial_data.costume_id or ""
                    )
                )
            except (ValueError, IndexError):
                self.costume_combo.setCurrentIndex(0)
            try:
                self.pose_combo.setCurrentIndex(
                    [pid for pid, _ in self.pose_items].index(
                        initial_data.pose_id or ""
                    )
                )
            except (ValueError, IndexError):
                self.pose_combo.setCurrentIndex(0)
            try:
                self.expression_combo.setCurrentIndex(
                    [eid for eid, _ in self.expression_items].index(
                        initial_data.expression_id or ""
                    )
                )
            except (ValueError, IndexError):
                self.expression_combo.setCurrentIndex(0)
        else:
            self.costume_combo.setCurrentIndex(0)
            self.pose_combo.setCurrentIndex(0)
            self.expression_combo.setCurrentIndex(0)

        # Layout
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("名前:"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("タグ:"))
        form_layout.addWidget(self.tags_edit)
        form_layout.addWidget(QLabel("追加プロンプト (Positive):"))
        form_layout.addWidget(self.prompt_edit)
        form_layout.addWidget(QLabel("追加ネガティブプロンプト (Negative):"))
        form_layout.addWidget(self.negative_prompt_edit)
        form_layout.addWidget(
            QLabel(
                "--- 状態の上書き (オプション) ---",
                styleSheet="color: #555; margin-top: 10px;",
            )
        )
        form_layout.addWidget(QLabel("衣装 (上書き):"))
        form_layout.addWidget(self.costume_combo)
        form_layout.addWidget(QLabel("ポーズ (上書き):"))
        form_layout.addWidget(self.pose_combo)
        form_layout.addWidget(QLabel("表情 (上書き):"))
        form_layout.addWidget(self.expression_combo)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @Slot()
    def accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return

        costume_idx = self.costume_combo.currentIndex()
        pose_idx = self.pose_combo.currentIndex()
        expression_idx = self.expression_combo.currentIndex()

        # Get ID from selected index (index 0 is "")
        costume_id = self.costume_items[costume_idx][0] if costume_idx > 0 else None
        pose_id = self.pose_items[pose_idx][0] if pose_idx > 0 else None
        expression_id = (
            self.expression_items[expression_idx][0] if expression_idx > 0 else None
        )

        self.saved_data = Direction(
            id=self.initial_data.id if self.initial_data else f"dir_{int(time.time())}",
            name=name,
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            prompt=self.prompt_edit.toPlainText().strip(),
            negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
            costume_id=costume_id,
            pose_id=pose_id,
            expression_id=expression_id,
        )
        super().accept()

    def get_data(self) -> Optional[Direction]:
        return self.saved_data


# --- スタイル定義 ---
modalOverlayStyle: Dict[str, Any] = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "right": 0,
    "bottom": 0,
    "backgroundColor": "rgba(0, 0, 0, 0.5)",
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "zIndex": 1000,
}
modalContentStyle: Dict[str, Any] = {
    "border": "1px solid #ccc",
    "padding": "20px",
    "backgroundColor": "white",
    "borderRadius": "8px",
    "width": "500px",
    "maxHeight": "90vh",
    "overflowY": "auto",
}
formGroupStyle: Dict[str, Any] = {
    "marginBottom": "10px",
    "display": "flex",
    "flexDirection": "column",
}
inputStyle: Dict[str, Any] = {
    "width": "95%",
    "padding": "8px",
    "marginTop": "4px",
    "fontSize": "14px",
}
