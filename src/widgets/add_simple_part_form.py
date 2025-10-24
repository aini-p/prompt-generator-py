# src/widgets/add_simple_part_form.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any
from ..models import PromptPartBase
import json


class AddSimplePartForm(QDialog):
    # objectType はウィンドウタイトル表示のみに使用
    def __init__(
        self, initial_data: Optional[PromptPartBase], objectType: str, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            f"{objectType.capitalize()} の編集"
            if initial_data
            else f"新規 {objectType.capitalize()} の追加"
        )
        self.initial_data = initial_data
        self.object_type = objectType.lower()  # ID生成用に保持
        self.saved_data: Optional[PromptPartBase] = None

        # UI Elements (PromptPartBase のフィールドのみ)
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.prompt_edit = QTextEdit()
        self.negative_prompt_edit = QTextEdit()

        # Set Initial Data
        if initial_data:
            self.name_edit.setText(getattr(initial_data, "name", ""))
            self.tags_edit.setText(", ".join(getattr(initial_data, "tags", [])))
            self.prompt_edit.setPlainText(getattr(initial_data, "prompt", ""))
            self.negative_prompt_edit.setPlainText(
                getattr(initial_data, "negative_prompt", "")
            )

        # Layout
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))  # ラベルを "Name" に固定
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("Tags (カンマ区切り):"))
        form_layout.addWidget(self.tags_edit)
        form_layout.addWidget(QLabel("プロンプト (Positive):"))
        form_layout.addWidget(self.prompt_edit)
        form_layout.addWidget(QLabel("ネガティブプロンプト (Negative):"))
        form_layout.addWidget(self.negative_prompt_edit)
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
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return

        # PromptPartBase としてデータを保存
        self.saved_data = PromptPartBase(
            id=getattr(self.initial_data, "id", None)
            or f"{self.object_type}_{int(time.time())}",
            name=name,
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            prompt=self.prompt_edit.toPlainText().strip(),
            negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
        )
        super().accept()

    def get_data(self) -> Optional[PromptPartBase]:
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
