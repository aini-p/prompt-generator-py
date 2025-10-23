# src/widgets/add_simple_part_form.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
    QComboBox,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any
from ..models import PromptPartBase, Work, Character


class AddSimplePartForm(QDialog):
    # Pass objectType as string for window title
    def __init__(
        self, initial_data: Optional[PromptPartBase], objectType: str, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            f"{objectType} の編集" if initial_data else f"新規 {objectType} の追加"
        )
        self.initial_data = initial_data
        self.object_type = objectType.lower()  # Use lower case for ID generation
        # ★ ウィンドウタイトルを objectType から生成
        self.setWindowTitle(
            f"{objectType.capitalize()} の編集"
            if initial_data
            else f"新規 {objectType.capitalize()} の追加"
        )
        self.saved_data: Optional[PromptPartBase] = None

        # UI Elements
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.prompt_edit = QTextEdit()
        self.negative_prompt_edit = QTextEdit()
        self.title_en_edit = QLineEdit()
        self.sns_tags_edit = QLineEdit()
        self.work_id_combo = QComboBox()

        # Set Initial Data
        if initial_data:
            # ★ Work かどうかで name/title_jp を使い分ける
            if isinstance(initial_data, Work):
                self.name_edit.setText(getattr(initial_data, "title_jp", ""))
                self.title_en_edit.setText(getattr(initial_data, "title_en", ""))
                self.sns_tags_edit.setText(getattr(initial_data, "sns_tags", ""))
            else:
                self.name_edit.setText(getattr(initial_data, "name", ""))
            # 共通の tags など
            self.tags_edit.setText(", ".join(initial_data.tags))
            self.prompt_edit.setPlainText(initial_data.prompt)
            self.negative_prompt_edit.setPlainText(initial_data.negative_prompt)
            # TODO: Character の work_id コンボボックスの初期選択

        # Layout
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        # ★ ラベルを objectType に応じて変更
        name_label = "Title (JP):" if self.object_type == "work" else "Name:"
        form_layout.addWidget(QLabel(name_label))
        form_layout.addWidget(self.name_edit)
        # ★ Work 専用フィールドの表示切り替え
        if self.object_type == "work":
            form_layout.addWidget(QLabel("Title (EN):"))
            form_layout.addWidget(self.title_en_edit)
            form_layout.addWidget(QLabel("SNS Tags:"))
            form_layout.addWidget(self.sns_tags_edit)
        form_layout.addWidget(QLabel("タグ (カンマ区切り):"))
        form_layout.addWidget(self.tags_edit)
        # ★ Prompt フィールドは Work/Character 以外で表示
        if self.object_type not in ["work", "character"]:
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
        name_or_title = self.name_edit.text().strip()
        if not name_or_title:
            label = "Title (JP)" if self.object_type == "work" else "Name"
            QMessageBox.warning(self, "入力エラー", f"{label} は必須です。")
            return

        self.saved_data = PromptPartBase(
            id=getattr(self.initial_data, "id", None)  # 編集ならID維持
            or f"{self.object_type}_{int(time.time())}",  # 新規なら生成
            name=name_or_title,  # title_jp も name に一時格納
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            prompt=self.prompt_edit.toPlainText().strip()
            if self.object_type not in ["work", "character"]
            else "",
            negative_prompt=self.negative_prompt_edit.toPlainText().strip()
            if self.object_type not in ["work", "character"]
            else "",
        )
        # ★ Work/Character の追加情報を保持 (MainWindow側で使うため)
        if self.object_type == "work":
            self.saved_data.title_en = self.title_en_edit.text().strip()
            self.saved_data.sns_tags = self.sns_tags_edit.text().strip()
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
