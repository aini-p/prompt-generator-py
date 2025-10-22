# src/widgets/add_actor_form.py
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
from PySide6.QtCore import Slot  # Import Slot if needed for explicit slot decoration
from typing import Optional, Dict, Any  # Import Dict and Any

# srcフォルダを基準にインポート (..はsrcフォルダを指す)
from ..models import Actor, FullDatabase


class AddActorForm(QDialog):
    def __init__(
        self, initial_data: Optional[Actor], db_dict: Dict[str, Dict], parent=None
    ):  # Use Dict type hint
        super().__init__(parent)
        self.setWindowTitle(
            "役者 (Actor) の編集" if initial_data else "新規 役者 (Actor) の追加"
        )
        self.db_dict = db_dict  # Pass the dictionary directly
        self.initial_data = initial_data
        self.saved_data: Optional[Actor] = None

        # --- UI要素の作成 ---
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.work_title_edit = QLineEdit()
        self.character_name_edit = QLineEdit()
        self.prompt_edit = QTextEdit()
        self.negative_prompt_edit = QTextEdit()
        self.costume_combo = QComboBox()
        self.pose_combo = QComboBox()
        self.expression_combo = QComboBox()

        # --- コンボボックスに選択肢を追加 ---
        # データベース辞書からIDと名前を取得
        self.costume_items = list(
            self.db_dict.get("costumes", {}).items()
        )  # [(id, obj), ...]
        self.pose_items = list(self.db_dict.get("poses", {}).items())
        self.expression_items = list(self.db_dict.get("expressions", {}).items())

        self.costume_combo.addItems(
            [c.name for _, c in self.costume_items]
            if self.costume_items
            else ["(なし)"]
        )
        self.pose_combo.addItems(
            [p.name for _, p in self.pose_items] if self.pose_items else ["(なし)"]
        )
        self.expression_combo.addItems(
            [e.name for _, e in self.expression_items]
            if self.expression_items
            else ["(なし)"]
        )

        # 初期データをフォームに設定
        if initial_data:
            self.name_edit.setText(initial_data.name)
            self.tags_edit.setText(", ".join(initial_data.tags))
            self.work_title_edit.setText(initial_data.work_title)
            self.character_name_edit.setText(initial_data.character_name)
            self.prompt_edit.setPlainText(initial_data.prompt)
            self.negative_prompt_edit.setPlainText(initial_data.negative_prompt)

            # コンボボックスの選択 (IDに基づいてインデックスを設定)
            try:
                costume_idx = [cid for cid, _ in self.costume_items].index(
                    initial_data.base_costume_id
                )
                self.costume_combo.setCurrentIndex(costume_idx)
            except (ValueError, IndexError):
                pass  # IDが見つからない場合は何もしない
            try:
                pose_idx = [pid for pid, _ in self.pose_items].index(
                    initial_data.base_pose_id
                )
                self.pose_combo.setCurrentIndex(pose_idx)
            except (ValueError, IndexError):
                pass
            try:
                expr_idx = [eid for eid, _ in self.expression_items].index(
                    initial_data.base_expression_id
                )
                self.expression_combo.setCurrentIndex(expr_idx)
            except (ValueError, IndexError):
                pass
        else:
            # 新規の場合のデフォルト値
            self.negative_prompt_edit.setPlainText("ugly, watermark")

        # --- レイアウト ---
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("名前:"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("タグ (カンマ区切り):"))
        form_layout.addWidget(self.tags_edit)
        form_layout.addWidget(QLabel("作品タイトル:"))
        form_layout.addWidget(self.work_title_edit)
        form_layout.addWidget(QLabel("キャラクター名:"))
        form_layout.addWidget(self.character_name_edit)
        form_layout.addWidget(QLabel("基本プロンプト (Positive):"))
        form_layout.addWidget(self.prompt_edit)
        form_layout.addWidget(QLabel("基本ネガティブプロンプト (Negative):"))
        form_layout.addWidget(self.negative_prompt_edit)
        form_layout.addWidget(QLabel("基本衣装:"))
        form_layout.addWidget(self.costume_combo)
        form_layout.addWidget(QLabel("基本ポーズ:"))
        form_layout.addWidget(self.pose_combo)
        form_layout.addWidget(QLabel("基本表情:"))
        form_layout.addWidget(self.expression_combo)

        layout.addLayout(form_layout)

        # --- 保存/キャンセルボタン ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(
            self.accept
        )  # OK/Save ボタンが押されたら accept() を呼ぶ
        button_box.rejected.connect(
            self.reject
        )  # Cancel ボタンが押されたら reject() を呼ぶ
        layout.addWidget(button_box)

    # --- accept() をオーバーライドしてデータを検証・保存 ---
    @Slot()  # Mark as a slot
    def accept(self):
        # フォームの入力値を取得
        name = self.name_edit.text().strip()
        prompt = self.prompt_edit.toPlainText().strip()
        work_title = self.work_title_edit.text().strip()
        character_name = self.character_name_edit.text().strip()

        if not all([name, prompt, work_title, character_name]):
            QMessageBox.warning(
                self,
                "入力エラー",
                "名前, プロンプト, 作品タイトル, キャラクター名は必須です。",
            )
            return  # accept を中断

        # コンボボックスから選択されたIDを取得
        costume_id = (
            self.costume_items[self.costume_combo.currentIndex()][0]
            if self.costume_items and self.costume_combo.currentIndex() >= 0
            else ""
        )
        pose_id = (
            self.pose_items[self.pose_combo.currentIndex()][0]
            if self.pose_items and self.pose_combo.currentIndex() >= 0
            else ""
        )
        expression_id = (
            self.expression_items[self.expression_combo.currentIndex()][0]
            if self.expression_items and self.expression_combo.currentIndex() >= 0
            else ""
        )

        self.saved_data = Actor(
            id=self.initial_data.id
            if self.initial_data
            else f"actor_{int(time.time())}",
            name=name,
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            prompt=prompt,
            negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
            base_costume_id=costume_id,
            base_pose_id=pose_id,
            base_expression_id=expression_id,
            work_title=work_title,
            character_name=character_name,
        )
        # データを保存したら、標準の accept 処理を呼ぶ
        super().accept()

    # --- MainWindow がデータを取得するためのメソッド ---
    def get_data(self) -> Optional[Actor]:
        return self.saved_data
