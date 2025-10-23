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
from ..models import Actor, FullDatabase, Work, Character


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
        self.work_combo = QComboBox()
        self.character_combo = QComboBox()
        self.prompt_edit = QTextEdit()
        self.negative_prompt_edit = QTextEdit()
        self.costume_combo = QComboBox()
        self.pose_combo = QComboBox()
        self.expression_combo = QComboBox()

        # --- コンボボックス初期化 ---
        self._populate_combos()

        self.work_combo.currentIndexChanged.connect(self._on_work_changed)

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
            try:
                current_character_id = initial_data.character_id
                character = self.db_dict.get("characters", {}).get(current_character_id)
                if character:
                    current_work_id = character.work_id
                    # Work コンボを選択
                    work_index = self.work_combo.findData(current_work_id)
                    if work_index >= 0:
                        self.work_combo.setCurrentIndex(work_index)
                    # Character コンボを更新して選択
                    self._update_character_combo(current_work_id, current_character_id)
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
        form_layout.addWidget(QLabel("登場作品 (Work):"))
        form_layout.addWidget(self.work_combo)
        form_layout.addWidget(QLabel("キャラクター (Character):"))
        form_layout.addWidget(self.character_combo)
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

    def _populate_combos(self):
        """関連コンボボックスの内容を作成します。"""
        self.work_combo.addItem("(未割り当て)", None)
        works = self.db_dict.get("works", {})
        sorted_works = sorted(works.values(), key=lambda w: w.title_jp.lower())
        for work in sorted_works:
            self.work_combo.addItem(f"{work.title_jp} ({work.id})", work.id)
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

    @Slot(int)
    def _on_work_changed(self, index: int):
        """Work コンボボックスの選択が変更されたときの処理。"""
        selected_work_id = self.work_combo.itemData(index)
        # Character コンボを更新 (選択はリセット)
        self._update_character_combo(selected_work_id, None)

    def _update_character_combo(
        self, work_id: Optional[str], select_char_id: Optional[str]
    ):
        """Character コンボボックスの内容を更新し、指定IDを選択します。"""
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        self.character_combo.addItem("(未選択)", None)
        ids = [None]

        filtered_chars = {}
        if work_id:
            all_chars = self.db_dict.get("characters", {})
            filtered_chars = {
                cid: c for cid, c in all_chars.items() if c.work_id == work_id
            }

        sorted_chars = sorted(filtered_chars.values(), key=lambda c: c.name.lower())
        for char in sorted_chars:
            self.character_combo.addItem(f"{char.name} ({char.id})", char.id)
            ids.append(char.id)

        # 指定された Character ID を選択
        try:
            index = ids.index(select_char_id) if select_char_id in ids else 0
            self.character_combo.setCurrentIndex(index)
        except ValueError:
            self.character_combo.setCurrentIndex(0)

        self.character_combo.blockSignals(False)

    # --- accept() をオーバーライドしてデータを検証・保存 ---
    @Slot()  # Mark as a slot
    def accept(self):
        # フォームの入力値を取得
        name = self.name_edit.text().strip()
        prompt = self.prompt_edit.toPlainText().strip()
        character_id = self.character_combo.currentData() or ""  # 未選択なら空文字

        # --- ★ バリデーション修正: Character が必須か？ (今回は name と prompt のみに) ---
        if not name or not prompt:
            QMessageBox.warning(
                self, "入力エラー", "名前 (Actor Name) と 基本プロンプト は必須です。"
            )
            return
        if not character_id:
            # キャラクター未選択は許可する (警告は出しても良い)
            # QMessageBox.warning(self, "確認", "キャラクターが選択されていません。")
            pass

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
            character_id=character_id,
            base_costume_id=costume_id,
            base_pose_id=pose_id,
            base_expression_id=expression_id,
        )
        # データを保存したら、標準の accept 処理を呼ぶ
        super().accept()

    # --- MainWindow がデータを取得するためのメソッド ---
    def get_data(self) -> Optional[Actor]:
        return self.saved_data
