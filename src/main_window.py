# src/main_window.py
import sys
import os
import json
import time
import traceback  # エラー詳細表示用にインポート
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QScrollArea,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QDialog,
    QLayout,
)
from PySide6.QtCore import Qt, Slot
from . import database as db
from .models import (
    Scene,
    Actor,
    Direction,
    PromptPartBase,
    StableDiffusionParams,
    Costume,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    SceneRole,
    RoleDirection,
    GeneratedPrompt,
    ImageGenerationTask,
    STORAGE_KEYS,
    FullDatabase,
    json_str_to_list,
)
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion
from typing import Dict, Optional, Any, List, Tuple, Literal, Union, TypeAlias

# --- 実際のフォームをインポート ---
try:
    from .widgets.add_actor_form import AddActorForm
    from .widgets.add_scene_form import AddSceneForm
    from .widgets.add_direction_form import AddDirectionForm
    from .widgets.add_simple_part_form import AddSimplePartForm

    FORMS_IMPORTED = True
    print("[DEBUG] 編集フォームウィジェットのインポートに成功しました。")
except ImportError as e:
    print(
        f"[DEBUG] 警告: 編集フォームウィジェットのインポートに失敗しました。プレースホルダーを使用します。エラー: {e}"
    )

    # フォールバック (プレースホルダー定義)
    class QDialogPlaceholder(QDialog):
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent", None))
            print("[DEBUG] プレースホルダーダイアログを使用しています。")
            title = "Placeholder Dialog"
            if args:
                if len(args) > 1 and isinstance(args[1], str):
                    title = f"Edit {args[1]}"
                elif args[0]:
                    title = f"Edit {args[0].__class__.__name__}"
                else:
                    title = f"New Item"
            self.setWindowTitle(title)

        def exec(self):
            QMessageBox.information(
                self, "プレースホルダー", "この編集機能はまだ実装されていません。"
            )
            return self.DialogCode.Rejected

        def get_data(self):
            return None

    AddActorForm = AddSceneForm = AddDirectionForm = AddSimplePartForm = (
        QDialogPlaceholder
    )
    FORMS_IMPORTED = False

# --- DatabaseKey の定義 ---
DatabaseKey = Literal[
    "actors",
    "costumes",
    "poses",
    "expressions",
    "directions",
    "backgrounds",
    "lighting",
    "compositions",
    "scenes",
    "sdParams",
]

# --- 汎用モーダルフォームの型 ---
ModalDataType = Union[Actor, Scene, Direction, PromptPartBase, None]
ModalState: TypeAlias = Dict[str, Any]  # {'type': str, 'data': ModalDataType}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)
        self.current_scene_id: Optional[str] = None
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.sd_params: StableDiffusionParams = StableDiffusionParams()
        self._load_all_data()
        self.actor_assignments: Dict[str, str] = {}
        self.generated_prompts: List[GeneratedPrompt] = []

        # メインウィジェットとレイアウト
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # スプリッター
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 左パネル
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400)
        left_panel.setMaximumWidth(600)
        splitter.addWidget(left_panel)

        # UI要素のセットアップ
        self._setup_data_management_ui(left_layout)
        self._setup_prompt_generation_ui(left_layout)

        # ライブラリ用スクロールエリア
        library_scroll = QScrollArea()
        library_scroll.setWidgetResizable(True)
        library_widget = QWidget()
        library_widget.setObjectName("library_widget")  # オブジェクト名を設定
        self.library_layout = QVBoxLayout(
            library_widget
        )  # library_layout をここで初期化
        library_widget.setLayout(self.library_layout)
        library_scroll.setWidget(library_widget)
        left_layout.addWidget(library_scroll)  # library_scroll を left_layout に追加

        self._setup_library_ui()  # library_layout が初期化された後に呼び出す

        left_layout.addStretch()

        # 右パネル
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        right_layout.addWidget(QLabel("Generated Prompts (Batch)"))
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        right_layout.addWidget(self.prompt_display_area)

        # スプリッターの初期サイズ
        splitter.setSizes([450, 750])

    # --- ↓↓↓ データ管理メソッド (save_all_data など) ↓↓↓ ---
    @Slot()
    def save_all_data(self):
        """メモリ上の全データをSQLiteデータベースに保存します。"""
        print("[DEBUG] save_all_data called.")
        try:
            # 各カテゴリのデータを保存
            for actor in self.db_data.get("actors", {}).values():
                db.save_actor(actor)  #
            for scene in self.db_data.get("scenes", {}).values():
                db.save_scene(scene)  #
            for direction in self.db_data.get("directions", {}).values():
                db.save_direction(direction)  #
            for costume in self.db_data.get("costumes", {}).values():
                db.save_costume(costume)  #
            for pose in self.db_data.get("poses", {}).values():
                db.save_pose(pose)  #
            for expression in self.db_data.get("expressions", {}).values():
                db.save_expression(expression)  #
            for background in self.db_data.get("backgrounds", {}).values():
                db.save_background(background)  #
            for lighting in self.db_data.get("lighting", {}).values():
                db.save_lighting(lighting)  #
            for composition in self.db_data.get("compositions", {}).values():
                db.save_composition(composition)  #

            # SDパラメータを保存
            db.save_sd_params(self.sd_params)  #

            QMessageBox.information(
                self, "Save Data", "全データをデータベースに保存しました。"
            )
            print("[DEBUG] All data saved to database.")
        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"データベースへの保存中にエラーが発生しました: {e}"
            )
            print(f"[DEBUG] Error saving data to DB: {e}")

    @Slot()
    def export_data(self):
        """現在のデータをJSONファイルにエクスポートします。"""
        print("[DEBUG] export_data called.")
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data to JSON",
            "",  # デフォルトディレクトリ
            "JSON Files (*.json);;All Files (*)",
            options=options,
        )
        if fileName:
            if not fileName.endswith(".json"):
                fileName += ".json"
            try:
                # データクラスを辞書に変換する準備
                export_dict = {}
                for key, data_dict in self.db_data.items():
                    # 各アイテムを dataclass.__dict__ を使って辞書に変換
                    export_dict[key] = {
                        item_id: item.__dict__ for item_id, item in data_dict.items()
                    }
                # sdParamsも辞書に変換
                export_dict["sdParams"] = self.sd_params.__dict__  #

                # Sceneのrolesとrole_directionsを再帰的に辞書に変換
                if "scenes" in export_dict:
                    for scene_id, scene_data in export_dict["scenes"].items():
                        # リスト内包表記で各要素を辞書に変換
                        scene_data["roles"] = [
                            r.__dict__ for r in scene_data.get("roles", [])
                        ]  #
                        scene_data["role_directions"] = [
                            rd.__dict__ for rd in scene_data.get("role_directions", [])
                        ]  #

                with open(fileName, "w", encoding="utf-8") as f:
                    json.dump(export_dict, f, indent=2, ensure_ascii=False)
                QMessageBox.information(
                    self,
                    "Export Success",
                    f"データを {fileName} にエクスポートしました。",
                )
                print(f"[DEBUG] Data exported to {fileName}")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Error",
                    f"JSONファイルへのエクスポート中にエラーが発生しました: {e}",
                )
                print(f"[DEBUG] Error exporting data: {e}")

    @Slot()
    def import_data(self):
        """JSONファイルからデータをインポートします。"""
        print("[DEBUG] import_data called.")
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "Import Data from JSON",
            "",  # デフォルトディレクトリ
            "JSON Files (*.json);;All Files (*)",
            options=options,
        )
        if fileName:
            confirm = QMessageBox.question(
                self,
                "Confirm Import",
                "現在のメモリ上のデータをJSONファイルの内容で上書きしますか？\n(データベースには保存されません。保存するにはSave to DBを押してください)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    with open(fileName, "r", encoding="utf-8") as f:
                        imported_data = json.load(f)

                    # --- インポートデータの検証とデータクラスへの変換 ---
                    new_db_data = {}
                    type_map = {  # models.py からインポートしたクラスを使用
                        "actors": Actor,
                        "scenes": Scene,
                        "directions": Direction,
                        "costumes": Costume,
                        "poses": Pose,
                        "expressions": Expression,
                        "backgrounds": Background,
                        "lighting": Lighting,
                        "compositions": Composition,
                    }

                    for key, klass in type_map.items():
                        new_db_data[key] = {}
                        items_dict = imported_data.get(key, {})
                        if not isinstance(items_dict, dict):
                            print(
                                f"[DEBUG] Warning: Expected dict for '{key}' in JSON, got {type(items_dict)}. Skipping."
                            )
                            continue
                        for item_id, item_data in items_dict.items():
                            try:
                                # Scene 特殊処理: roles と role_directions を dataclass に変換
                                if klass == Scene:
                                    item_data["roles"] = [
                                        SceneRole(**r)
                                        for r in item_data.get("roles", [])
                                    ]
                                    item_data["role_directions"] = [
                                        RoleDirection(**rd)
                                        for rd in item_data.get("role_directions", [])
                                    ]

                                new_db_data[key][item_id] = klass(
                                    **item_data
                                )  # ** で辞書を展開してインスタンス化
                            except TypeError as te:
                                print(
                                    f"[DEBUG] Import Warning: Skipping item '{item_id}' in '{key}' due to TypeError: {te}. Data: {item_data}"
                                )
                            except Exception as ex:
                                print(
                                    f"[DEBUG] Import Warning: Skipping item '{item_id}' in '{key}' due to unexpected error: {ex}. Data: {item_data}"
                                )

                    # SD Params のインポートと変換
                    sd_params_data = imported_data.get("sdParams", {})
                    try:
                        # JSONの値を正しい型に変換しようと試みる
                        cleaned_sd_data = {}
                        default_sd = StableDiffusionParams()  # デフォルト値取得用
                        for field_name, default_value in default_sd.__dict__.items():
                            imported_value = sd_params_data.get(field_name)
                            if imported_value is not None:
                                try:
                                    target_type = type(
                                        default_value
                                    )  # デフォルト値の型を取得
                                    cleaned_sd_data[field_name] = target_type(
                                        imported_value
                                    )  # 型変換
                                except (ValueError, TypeError):
                                    print(
                                        f"[DEBUG] SD Param Import Warning: Could not convert '{field_name}' value '{imported_value}' to {target_type}. Using default."
                                    )
                                    cleaned_sd_data[field_name] = (
                                        default_value  # エラー時はデフォルト値
                                    )
                            else:
                                cleaned_sd_data[field_name] = (
                                    default_value  # JSONにない場合もデフォルト値
                                )

                        self.sd_params = StableDiffusionParams(**cleaned_sd_data)
                        print("[DEBUG] SD Params imported and converted.")
                    except TypeError as te:
                        print(
                            f"[DEBUG] Import Error: Could not create StableDiffusionParams instance: {te}. Using defaults. Data: {sd_params_data}"
                        )
                        self.sd_params = StableDiffusionParams()  # エラー時はデフォルト
                    except Exception as ex:
                        print(
                            f"[DEBUG] Import Error: Unexpected error importing SD Params: {ex}. Using defaults. Data: {sd_params_data}"
                        )
                        self.sd_params = StableDiffusionParams()  # エラー時はデフォルト

                    # --- メモリ上のデータを更新 ---
                    self.db_data = new_db_data
                    # current_scene_idがインポートデータに存在するか確認、なければ先頭に
                    scenes_dict = self.db_data.get("scenes", {})
                    if self.current_scene_id not in scenes_dict:
                        self.current_scene_id = next(iter(scenes_dict), None)

                    self.actor_assignments = {}  # インポート後は割り当てリセット
                    self.generated_prompts = []  # インポート後は生成プロンプトリセット

                    QMessageBox.information(
                        self,
                        "Import Success",
                        f"データを {fileName} からメモリにインポートしました。\n変更を永続化するには 'Save to DB' を押してください。",
                    )
                    print(f"[DEBUG] Data imported from {fileName} into memory.")
                    self.update_ui_after_data_change()  # UIを更新してインポート結果を反映

                except FileNotFoundError:
                    QMessageBox.critical(
                        self, "Import Error", f"ファイルが見つかりません: {fileName}"
                    )
                    print(f"[DEBUG] Error importing data: File not found {fileName}")
                except json.JSONDecodeError as jde:
                    QMessageBox.critical(
                        self, "Import Error", f"JSONファイルの解析に失敗しました: {jde}"
                    )
                    print(f"[DEBUG] Error importing data: JSON decode error {jde}")
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Import Error",
                        f"データのインポート中に予期せぬエラーが発生しました: {e}",
                    )
                    print(f"[DEBUG] Error importing data: {e}")
                    traceback.print_exc()  # 詳細なエラーを出力

    # --- ↑↑↑ データ管理メソッド (save_all_data など) ↑↑↑ ---

    def _load_all_data(self):
        print("[DEBUG] _load_all_data called.")
        try:
            self.db_data["actors"] = db.load_actors()  #
            self.db_data["scenes"] = db.load_scenes()  #
            self.db_data["directions"] = db.load_directions()  #
            self.db_data["costumes"] = db.load_costumes()  #
            self.db_data["poses"] = db.load_poses()  #
            self.db_data["expressions"] = db.load_expressions()  #
            self.db_data["backgrounds"] = db.load_backgrounds()  #
            self.db_data["lighting"] = db.load_lighting()  #
            self.db_data["compositions"] = db.load_compositions()  #
            self.sd_params = db.load_sd_params()  #
            print("[DEBUG] Data loaded successfully from database.")

            scenes_dict = self.db_data.get("scenes", {})
            print(f"[DEBUG] Loaded {len(scenes_dict)} scenes.")
            if scenes_dict:
                # 現在のシーンIDが無効なら最初のシーンを選択
                if self.current_scene_id not in scenes_dict:
                    print(
                        f"[DEBUG] Current scene ID '{self.current_scene_id}' is invalid or None."
                    )
                    self.current_scene_id = next(
                        iter(scenes_dict), None
                    )  # 辞書の最初のキーを取得
                    print(
                        f"[DEBUG] Setting current scene ID to: {self.current_scene_id}"
                    )
            else:
                self.current_scene_id = None
                print("[DEBUG] No scenes found.")
            print(f"[DEBUG] Initial scene ID set to: {self.current_scene_id}")

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load data: {e}")
            print(f"[DEBUG] DB load error: {e}")
            # エラー時もキーは空辞書で初期化しておく
            self.db_data = {k: {} for k in STORAGE_KEYS if k != "sdParams"}  #
            self.sd_params = StableDiffusionParams()  #
            self.current_scene_id = None

    def _setup_data_management_ui(self, parent_layout):
        group = QGroupBox("Data Management")
        layout = QHBoxLayout()
        group.setLayout(layout)

        save_btn = QPushButton("💾 Save to DB")
        save_btn.clicked.connect(self.save_all_data)  # ここで接続

        export_btn = QPushButton("📤 Export JSON")
        export_btn.clicked.connect(self.export_data)  # ここで接続

        import_btn = QPushButton("📥 Import JSON")
        import_btn.clicked.connect(self.import_data)  # ここで接続

        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addWidget(import_btn)
        parent_layout.addWidget(group)

    def _setup_prompt_generation_ui(self, parent_layout):
        print("[DEBUG] _setup_prompt_generation_ui called.")
        group = QGroupBox("Prompt Generation")
        self.prompt_gen_layout = QVBoxLayout()
        group.setLayout(self.prompt_gen_layout)

        # シーン選択
        scene_layout = QHBoxLayout()
        scene_layout.addWidget(QLabel("1. Select Scene:"))
        self.scene_combo = QComboBox()
        self.update_scene_combo()  # コンボボックスの内容更新
        self.scene_combo.currentIndexChanged.connect(self.on_scene_changed)
        scene_layout.addWidget(self.scene_combo)
        self.prompt_gen_layout.addLayout(scene_layout)

        # 役割割り当て (動的UI用ウィジェット)
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        print(
            "[DEBUG] _setup_prompt_generation_ui: Initial role_assignment_widget created."
        )
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)
        self.build_role_assignment_ui()  # 初回UI構築

        # ボタン
        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(self.generate_prompts)

        execute_btn = QPushButton("🚀 Execute Image Generation (Run Batch)")
        execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        execute_btn.clicked.connect(self.execute_generation)

        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(execute_btn)
        parent_layout.addWidget(group)
        print("[DEBUG] _setup_prompt_generation_ui complete.")

    def update_scene_combo(self):
        print("[DEBUG] update_scene_combo called.")
        self.scene_combo.blockSignals(True)  # 更新中のシグナル発生をブロック
        self.scene_combo.clear()

        scene_list = list(self.db_data.get("scenes", {}).values())
        print(f"[DEBUG] update_scene_combo: Found {len(scene_list)} scenes.")

        if not scene_list:
            self.scene_combo.addItem("No scenes available")
            self.scene_combo.setEnabled(False)
            print("[DEBUG] update_scene_combo: No scenes available.")
        else:
            scene_ids = [s.id for s in scene_list]
            self.scene_combo.addItems([s.name for s in scene_list])  # シーン名を追加

            current_scene_index = 0
            # 現在選択中のシーンIDがあれば、そのインデックスを探す
            if self.current_scene_id and self.current_scene_id in scene_ids:
                try:
                    current_scene_index = scene_ids.index(self.current_scene_id)
                except ValueError:
                    print(
                        f"[DEBUG] update_scene_combo: current_id '{self.current_scene_id}' not found."
                    )
                    # 見つからなければ最初のシーンを選択状態にする
                    self.current_scene_id = scene_ids[0]
                    current_scene_index = 0
            elif scene_list:  # current_scene_id が None の場合も最初のシーンを選択
                self.current_scene_id = scene_ids[0]
                current_scene_index = 0
                print(
                    f"[DEBUG] update_scene_combo: set to first: {self.current_scene_id}"
                )

            print(
                f"[DEBUG] update_scene_combo: Setting index to {current_scene_index} (ID: {self.current_scene_id})"
            )
            self.scene_combo.setCurrentIndex(current_scene_index)
            self.scene_combo.setEnabled(True)

        self.scene_combo.blockSignals(False)  # シグナルブロック解除
        print("[DEBUG] update_scene_combo complete.")

    def build_role_assignment_ui(self):
        """Dynamically builds the UI for assigning actors to roles
        INSIDE the current self.role_assignment_widget."""
        print(
            f"[DEBUG] build_role_assignment_ui called for scene ID: {self.current_scene_id}"
        )

        layout = self.role_assignment_widget.layout()
        if layout is None:
            print(
                "[DEBUG] No layout found on role_assignment_widget, creating new QVBoxLayout."
            )
            layout = QVBoxLayout()
            self.role_assignment_widget.setLayout(layout)
        else:
            print("[DEBUG] Clearing existing role assignment layout...")
            item = layout.takeAt(0)
            while item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    layout_item = item.layout()
                    if layout_item is not None:
                        item_inner = layout_item.takeAt(0)
                        while item_inner is not None:
                            widget_inner = item_inner.widget()
                            if widget_inner is not None:
                                widget_inner.deleteLater()
                            layout_inner = item_inner.layout()
                            if layout_inner is not None:
                                layout_inner.deleteLater()
                            item_inner = layout_item.takeAt(0)
                        layout_item.deleteLater()
                item = layout.takeAt(0)
            print("[DEBUG] Existing role assignment layout cleared.")

        layout.addWidget(QLabel("2. Assign Actors to Roles:"))
        current_scene = (
            self.db_data.get("scenes", {}).get(self.current_scene_id)
            if self.current_scene_id
            else None
        )
        if not current_scene:
            layout.addWidget(QLabel("No scene selected."))
            layout.addStretch()
            print("[DEBUG] build_role_assignment_ui: No scene selected.")
            return

        actor_list = list(self.db_data.get("actors", {}).values())
        actor_names = ["-- Select Actor --"] + [a.name for a in actor_list]
        actor_ids = [""] + [a.id for a in actor_list]
        print(f"[DEBUG] build_role_assignment_ui: Found {len(actor_list)} actors.")

        if not current_scene.roles:  #
            layout.addWidget(QLabel("(このシーンには配役が定義されていません)"))
            print("[DEBUG] build_role_assignment_ui: Current scene has no roles.")

        print(
            f"[DEBUG] build_role_assignment_ui: Building UI for {len(current_scene.roles)} roles..."  #
        )
        for role in current_scene.roles:  #
            print(f"[DEBUG] Creating UI for role: {role.id} ({role.name_in_scene})")  #
            role_layout = QHBoxLayout()
            label_text = f"{role.name_in_scene} ([{role.id.upper()}])"  #
            role_layout.addWidget(QLabel(label_text))
            combo = QComboBox()
            combo.addItems(actor_names)

            assigned_actor_id = self.actor_assignments.get(role.id)
            current_index = 0
            if assigned_actor_id and assigned_actor_id in actor_ids:
                try:
                    current_index = actor_ids.index(assigned_actor_id)
                except ValueError:
                    print(
                        f"[DEBUG] Warn: Assigned actor ID '{assigned_actor_id}' not found."
                    )
            combo.setCurrentIndex(current_index)
            # ラムダ関数で role.id と actor_ids をキャプチャ
            combo.currentIndexChanged.connect(
                lambda index, r_id=role.id, ids=list(actor_ids): self.on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_layout.addWidget(combo)
            layout.addLayout(role_layout)

        layout.addStretch()
        self.role_assignment_widget.adjustSize()
        if self.prompt_gen_layout:
            self.prompt_gen_layout.activate()

        print("[DEBUG] build_role_assignment_ui complete.")

    @Slot(int)
    def on_scene_changed(self, index):
        print(f"[DEBUG] on_scene_changed called with index: {index}")
        scene_list = list(self.db_data.get("scenes", {}).values())
        if 0 <= index < len(scene_list):
            new_scene_id = scene_list[index].id
            print(f"[DEBUG] Selected scene ID from list: {new_scene_id}")
            if new_scene_id != self.current_scene_id:
                print(
                    f"[DEBUG] Scene ID changed! Old: {self.current_scene_id}, New: {new_scene_id}"
                )
                self.current_scene_id = new_scene_id
                # シーンが変わったら割り当てと生成済みプロンプトをリセット
                self.actor_assignments = {}
                self.generated_prompts = []
                print("[DEBUG] Calling build_role_assignment_ui...")
                self.build_role_assignment_ui()  # 役割割り当てUIを再構築
                print("[DEBUG] Returned from build_role_assignment_ui.")
                self.update_prompt_display()  # プロンプト表示エリアをクリア
            else:
                print("[DEBUG] Scene index changed, but ID is the same.")
        else:
            print(f"[DEBUG] Invalid scene index selected: {index}")

    def _setup_library_ui(self):
        """Populates the library editing section."""
        print("[DEBUG] _setup_library_ui called.")
        if hasattr(self, "library_layout") and self.library_layout is not None:
            print(
                f"[DEBUG] Clearing library layout. Item count: {self.library_layout.count()}"
            )
            while self.library_layout.count() > 0:
                item = self.library_layout.takeAt(self.library_layout.count() - 1)
                if item is None:
                    print(
                        "[DEBUG] takeAt returned None unexpectedly in library layout."
                    )
                    continue
                widget = item.widget()
                if widget is not None:
                    print(f"[DEBUG] Deleting library widget: {widget}")
                    widget.deleteLater()
                else:
                    layout_item = item.layout()
                    if layout_item is not None:
                        print(f"[DEBUG] Deleting nested library layout: {layout_item}")
                        while layout_item.count() > 0:
                            nested_item = layout_item.takeAt(layout_item.count() - 1)
                            nested_widget = nested_item.widget()
                            if nested_widget:
                                nested_widget.deleteLater()
                            nested_layout = nested_item.layout()
                            if nested_layout:
                                nested_layout.deleteLater()
                        layout_item.deleteLater()
            print("[DEBUG] Finished clearing library layout.")
        else:
            print(
                "[DEBUG] self.library_layout is None or doesn't exist yet, cannot clear."
            )

        if not hasattr(self, "library_layout") or self.library_layout is None:
            print("[DEBUG] ERROR: self.library_layout is missing in _setup_library_ui!")
            # library_widget をオブジェクト名で検索してリカバリ試行
            library_widget = self.findChild(QWidget, "library_widget")
            if library_widget:
                self.library_layout = QVBoxLayout(library_widget)
                print("[DEBUG] Recovered library_layout.")
            else:
                print("[DEBUG] Could not find library_widget to recover layout.")
                return

        library_group = QGroupBox("Library Editing")
        library_group_layout = QVBoxLayout()
        library_group.setLayout(library_group_layout)
        self.library_layout.addWidget(library_group)
        print("[DEBUG] Added new 'Library Editing' QGroupBox.")

        # --- SD Params Editor ---
        sd_group = QGroupBox("Stable Diffusion Parameters")
        # sd_group.setCheckable(True)
        # sd_group.setChecked(False)
        sd_layout = QFormLayout()
        sd_group.setLayout(sd_layout)
        library_group_layout.addWidget(sd_group)

        self.sd_steps_spin = getattr(
            self, "sd_steps_spin", QSpinBox(minimum=1, maximum=200)
        )
        self.sd_sampler_edit = getattr(self, "sd_sampler_edit", QLineEdit())
        self.sd_cfg_spin = getattr(
            self,
            "sd_cfg_spin",
            QDoubleSpinBox(minimum=1.0, maximum=30.0, singleStep=0.5),
        )
        self.sd_seed_spin = getattr(
            self, "sd_seed_spin", QSpinBox(minimum=-1, maximum=2**31 - 1)
        )
        self.sd_width_spin = getattr(
            self, "sd_width_spin", QSpinBox(minimum=64, maximum=4096, singleStep=64)
        )
        self.sd_height_spin = getattr(
            self, "sd_height_spin", QSpinBox(minimum=64, maximum=4096, singleStep=64)
        )
        self.sd_denoising_spin = getattr(
            self,
            "sd_denoising_spin",
            QDoubleSpinBox(minimum=0.0, maximum=1.0, singleStep=0.05),
        )
        self.sd_steps_spin.setValue(self.sd_params.steps)  #
        self.sd_sampler_edit.setText(self.sd_params.sampler_name)  #
        self.sd_cfg_spin.setValue(self.sd_params.cfg_scale)  #
        self.sd_seed_spin.setValue(self.sd_params.seed)  #
        self.sd_width_spin.setValue(self.sd_params.width)  #
        self.sd_height_spin.setValue(self.sd_params.height)  #
        self.sd_denoising_spin.setValue(self.sd_params.denoising_strength)  #
        try:
            self.sd_steps_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_steps_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "steps", v)
        )
        try:
            self.sd_sampler_edit.textChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_sampler_edit.textChanged.connect(
            lambda t: setattr(self.sd_params, "sampler_name", t)
        )
        try:
            self.sd_cfg_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_cfg_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "cfg_scale", v)
        )
        try:
            self.sd_seed_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_seed_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "seed", v)
        )
        try:
            self.sd_width_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_width_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "width", v)
        )
        try:
            self.sd_height_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_height_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "height", v)
        )
        try:
            self.sd_denoising_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_denoising_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "denoising_strength", v)
        )
        if not sd_layout.rowCount() > 0:
            sd_layout.addRow("Steps:", self.sd_steps_spin)
            sd_layout.addRow("Sampler Name:", self.sd_sampler_edit)
            sd_layout.addRow("CFG Scale:", self.sd_cfg_spin)
            sd_layout.addRow("Seed (-1 Random):", self.sd_seed_spin)
            sd_layout.addRow("Width:", self.sd_width_spin)
            sd_layout.addRow("Height:", self.sd_height_spin)
            sd_layout.addRow("Denoising (img2img):", self.sd_denoising_spin)

        # --- Collapsible Library Sections ---
        library_items: List[Tuple[str, str, str]] = [  #
            ("Scenes", "scenes", "SCENE"),
            ("Actors", "actors", "ACTOR"),
            ("Directions", "directions", "DIRECTION"),
            ("Costumes", "costumes", "COSTUME"),
            ("Poses", "poses", "POSE"),
            ("Expressions", "expressions", "EXPRESSION"),
            ("Backgrounds", "backgrounds", "BACKGROUND"),
            ("Lighting", "lighting", "LIGHTING"),
            ("Compositions", "compositions", "COMPOSITION"),
        ]
        print(f"[DEBUG] Setting up {len(library_items)} library sections...")
        for title, db_key_str, modal_type_str in library_items:
            db_key: DatabaseKey = db_key_str
            modal_type = modal_type_str
            if db_key not in self.db_data:
                print(f"[DEBUG] Key '{db_key}' not found in db_data.")
                continue

            # グループボックス (リストと追加ボタンを含む)
            group = QGroupBox(title)
            # group.setCheckable(True)
            # group.setChecked(False)
            layout_inside_group = QVBoxLayout()
            group.setLayout(layout_inside_group)

            add_btn = QPushButton(f"＋ Add New {title[:-1]}")
            add_btn.clicked.connect(
                lambda checked=False, mt=modal_type: self.open_edit_dialog(mt, None)
            )
            layout_inside_group.addWidget(add_btn)

            list_widget = QListWidget()
            list_widget.setMaximumHeight(150)
            items = self.db_data.get(db_key, {})
            if isinstance(items, dict):
                for item_id, item_obj in items.items():
                    item_name = getattr(item_obj, "name", "Unnamed")
                    item_id_str = getattr(item_obj, "id", None)
                    if item_id_str:
                        list_item = QListWidgetItem(f"{item_name} ({item_id_str})")
                        # UserRole に ID を格納
                        list_item.setData(Qt.ItemDataRole.UserRole, item_id_str)
                        list_widget.addItem(list_item)
            else:
                print(
                    f"[DEBUG] Warning: Expected dict for db_key '{db_key}', but got {type(items)}."
                )
            layout_inside_group.addWidget(list_widget)

            # --- ★ 編集・削除ボタン (グループの外) ---
            btn_layout = QHBoxLayout()
            edit_btn = QPushButton("✏️ Edit Selected")
            delete_btn = QPushButton("🗑️ Delete Selected")
            # ラムダ関数で list_widget インスタンスをキャプチャ
            edit_btn.clicked.connect(
                lambda checked=False,
                lw=list_widget,
                mt=modal_type,
                dk=db_key: self.edit_selected_item(lw, mt, dk)
            )
            delete_btn.clicked.connect(
                lambda checked=False,
                lw=list_widget,
                dk=db_key: self.delete_selected_item(lw, dk)
            )
            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(delete_btn)

            # library_group_layout (メインのライブラリレイアウト) に追加
            library_group_layout.addWidget(group)  # グループボックス
            library_group_layout.addLayout(btn_layout)  # ボタンレイアウト

        print("[DEBUG] Library sections setup complete.")

    def handleSavePart(self, db_key: DatabaseKey, part: Any):
        """Saves a single part (Actor, Scene, etc.) to the in-memory db_data."""
        if not hasattr(part, "id"):
            print(
                f"[DEBUG] Error in handleSavePart: Saved data has no 'id'. Data: {part}"
            )
            return
        print(
            f"[DEBUG] handleSavePart called for db_key='{db_key}', part_id='{part.id}'"
        )

        if db_key in self.db_data:
            if not isinstance(self.db_data[db_key], dict):
                print(
                    f"[DEBUG] Warning: self.db_data['{db_key}'] is not a dict. Reinitializing."
                )
                self.db_data[db_key] = {}
            self.db_data[db_key][part.id] = part
            print(f"[DEBUG] Part {part.id} saved/updated in self.db_data['{db_key}'].")
        else:
            print(f"[DEBUG] Error: Invalid db_key '{db_key}' passed to handleSavePart.")
            return

        # シーンが保存されたら、現在のシーンIDを更新し、関連UIも更新
        if db_key == "scenes":
            print(f"[DEBUG] Scene saved, setting current_scene_id to {part.id}")
            self.current_scene_id = part.id
            print("[DEBUG] Triggering UI updates after scene save...")
            self.update_scene_combo()  # コンボボックス更新
            self.build_role_assignment_ui()  # 役割割り当てUI更新
            self.update_prompt_display()  # プロンプト表示クリア

    def handleDeletePart(self, db_key: DatabaseKey, partId: str):
        """Deletes a single part from the in-memory db_data."""
        # アイテム名を取得 (存在しない場合も考慮)
        item_to_delete = self.db_data.get(db_key, {}).get(partId)
        partName = getattr(item_to_delete, "name", "Item") if item_to_delete else "Item"

        print(
            f"[DEBUG] handleDeletePart called for db_key='{db_key}', partId='{partId}' ({partName})"
        )

        # 確認ダイアログ (delete_selected_item で表示する前提)
        if db_key in self.db_data and partId in self.db_data[db_key]:
            print(f"[DEBUG] Deleting {partId} from self.db_data['{db_key}']...")
            del self.db_data[db_key][partId]

            # 関連データの更新
            if db_key == "actors":
                print("[DEBUG] Actor deleted, clearing assignments...")
                # 削除されたActor IDを参照している割り当てを削除
                new_assignments = {
                    k: v for k, v in self.actor_assignments.items() if v != partId
                }
                self.actor_assignments = new_assignments
                self.build_role_assignment_ui()  # UI再構築が必要な場合がある
            if db_key == "scenes" and partId == self.current_scene_id:
                print(
                    "[DEBUG] Current scene deleted, selecting first available scene..."
                )
                # 利用可能な最初のシーンを選択し直す
                self.current_scene_id = next(iter(self.db_data.get("scenes", {})), None)
                # UI更新は update_ui_after_data_change で行われるか、別途呼ぶ
                # self.update_scene_combo()

            print(f"[DEBUG] Deletion from db_data complete for {partId}.")
        else:
            print(f"[DEBUG] Item {partId} not found in {db_key}, cannot delete.")

    def LibraryList(self, db_key: DatabaseKey, modal_type: str) -> QWidget:
        """Creates a widget containing a list and edit/delete buttons for a library type."""
        # このメソッドは _setup_library_ui 内で直接UIを構築するように変更されたため、
        # 現在は使用されていません。将来的に再利用する可能性のため残しておきます。
        print(f"[DEBUG] LibraryList method called for: {db_key} (Currently unused)")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        # ... (以前の LibraryList の中身) ...
        return widget

    @Slot(str, str)
    def on_actor_assigned(self, role_id, actor_id):
        print(
            f"[DEBUG] on_actor_assigned called for Role ID: {role_id}, Actor ID: '{actor_id}'"
        )
        if actor_id:  # 有効なActor IDが選択された場合
            self.actor_assignments[role_id] = actor_id
            print(f"[DEBUG] Assigned actor {actor_id} to role {role_id}")
        else:  # "-- Select Actor --" などが選択された場合
            if role_id in self.actor_assignments:
                del self.actor_assignments[role_id]
                print(f"[DEBUG] Unassigned actor from role {role_id}")
            else:
                print(f"[DEBUG] Role {role_id} was already unassigned.")
        print(f"[DEBUG] Current assignments: {self.actor_assignments}")
        # 割り当てが変わったら生成済みプロンプトはリセット
        self.generated_prompts = []
        self.update_prompt_display()  # プロンプト表示エリアをクリア

    @Slot()
    def generate_prompts(self):
        if not self.current_scene_id:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return
        current_scene = self.db_data["scenes"].get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(self, "Generate", "Selected scene data not found.")
            return

        # 全ての役割にアクターが割り当てられているかチェック
        missing_roles = [
            r.name_in_scene  #
            for r in current_scene.roles  #
            if r.id not in self.actor_assignments  #
        ]
        if missing_roles:
            QMessageBox.warning(
                self,
                "Generate",
                f"Assign actors to all roles: {', '.join(missing_roles)}",
            )
            return

        try:
            # プロンプト生成関数を呼び出す
            self.generated_prompts: List[GeneratedPrompt] = generate_batch_prompts(
                self.current_scene_id, self.actor_assignments, self.db_data
            )
            self.update_prompt_display()  # 結果を表示
        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error", f"Error generating prompts: {e}"
            )
            print(f"[DEBUG] Prompt generation error: {e}")
            traceback.print_exc()  # 詳細なエラーを出力

    @Slot()
    def execute_generation(self):
        if not self.generated_prompts:
            QMessageBox.warning(
                self, "Execute", "Please generate prompt previews first."
            )
            return
        current_scene = self.db_data["scenes"].get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(
                self, "Execute", "Cannot execute without a selected scene."
            )
            return

        try:
            # 画像生成タスクリストを作成
            tasks = create_image_generation_tasks(
                self.generated_prompts, self.sd_params, current_scene
            )
            if not tasks:
                QMessageBox.warning(self, "Execute", "No tasks were generated.")
                return

            # バッチ実行関数を呼び出す
            success, message = run_stable_diffusion(tasks)
            if success:
                QMessageBox.information(self, "Execute", message)
            else:
                QMessageBox.critical(self, "Execution Error", message)
        except Exception as e:
            QMessageBox.critical(
                self, "Execution Error", f"An unexpected error occurred: {e}"
            )
            print(f"[DEBUG] Execution error: {e}")
            traceback.print_exc()  # 詳細なエラーを出力

    def update_prompt_display(self):
        """Updates the right panel's text area."""
        print("[DEBUG] update_prompt_display called.")
        if not self.generated_prompts:
            self.prompt_display_area.setPlainText("Press 'Generate Prompt Preview'.")
            print("[DEBUG] No prompts to display.")
            return

        display_text = ""
        print(f"[DEBUG] Displaying {len(self.generated_prompts)} generated prompts.")
        for p in self.generated_prompts:  # p は GeneratedPrompt オブジェクト
            display_text += f"--- {p.name} ---\n"
            display_text += f"Positive:\n{p.positive}\n\n"
            display_text += f"Negative:\n{p.negative}\n"
            display_text += "------------------------------------\n\n"
        self.prompt_display_area.setPlainText(display_text)
        print("[DEBUG] Prompt display area updated.")

    def update_ui_after_data_change(self):
        """データ変更後にUI全体を更新するためのヘルパー関数"""
        print("[DEBUG] update_ui_after_data_change called.")
        self.update_scene_combo()  # シーン選択更新
        self._setup_library_ui()  # ライブラリUI再構築
        self.build_role_assignment_ui()  # 役割割り当てUI再構築
        self.generated_prompts = []  # 生成済みプロンプトリセット
        self.update_prompt_display()  # プロンプト表示クリア
        print("[DEBUG] update_ui_after_data_change complete.")

    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
        """Opens the appropriate dialog based on modal_type."""
        dialog: Optional[QDialog] = None
        # modal_type 文字列から対応する db_key を取得
        db_key_map = {
            "ACTOR": "actors",
            "SCENE": "scenes",
            "DIRECTION": "directions",
            "COSTUME": "costumes",
            "POSE": "poses",
            "EXPRESSION": "expressions",
            "BACKGROUND": "backgrounds",
            "LIGHTING": "lighting",
            "COMPOSITION": "compositions",
        }
        db_key = db_key_map.get(modal_type)
        if not db_key:
            QMessageBox.warning(
                self, "Error", f"Invalid modal type for dialog: {modal_type}"
            )
            return

        print(
            f"[DEBUG] open_edit_dialog called for type: {modal_type}, data: {'Exists' if item_data else 'None'}"
        )
        try:
            # modal_type に応じて適切なフォームクラスをインスタンス化
            if modal_type == "ACTOR":
                dialog = AddActorForm(item_data, self.db_data, self)  #
            elif modal_type == "SCENE":
                dialog = AddSceneForm(item_data, self.db_data, self)  #
            elif modal_type == "DIRECTION":
                dialog = AddDirectionForm(item_data, self.db_data, self)  #
            elif modal_type in [  # SimplePartForm を使用するタイプ
                "COSTUME",
                "POSE",
                "EXPRESSION",
                "BACKGROUND",
                "LIGHTING",
                "COMPOSITION",
            ]:
                dialog = AddSimplePartForm(item_data, modal_type, self)
            else:
                QMessageBox.warning(
                    self,
                    "Not Implemented",
                    f"Dialog for '{modal_type}' not implemented.",
                )
                return
            print(f"[DEBUG] Dialog instance created: {dialog}")
        except Exception as e:
            QMessageBox.critical(
                self, "Dialog Error", f"Failed to create dialog for {modal_type}: {e}"
            )
            print(f"[DEBUG] Error creating dialog: {e}")
            traceback.print_exc()  # 詳細なエラーを出力
            return

        if dialog:
            print("[DEBUG] Executing dialog...")
            result = dialog.exec()
            print(f"[DEBUG] Dialog exec finished with result: {result}")

            if result == QDialog.DialogCode.Accepted:
                print("[DEBUG] Dialog accepted.")
                # get_data メソッドが存在するか確認
                if hasattr(dialog, "get_data") and callable(dialog.get_data):
                    saved_data = dialog.get_data()
                    # db_key が有効で、データが返された場合のみ保存処理
                    if saved_data and db_key in self.db_data:
                        print(
                            f"[DEBUG] Dialog returned data: {saved_data.id}. Calling handleSavePart."
                        )
                        self.handleSavePart(
                            db_key, saved_data
                        )  # メモリ上のデータを更新
                        self.update_ui_after_data_change()  # UI全体を更新
                    elif not db_key:
                        print("[DEBUG] Error: db_key is missing for save operation.")
                    elif (
                        db_key not in self.db_data
                    ):  # db_key が MainWindow.db_data の有効なキーかチェック
                        print(
                            f"[DEBUG] Error: db_key '{db_key}' is not a valid key in self.db_data."
                        )
                    else:  # saved_data が None の場合
                        print("[DEBUG] Dialog accepted but returned no data.")
                else:
                    print(
                        f"[DEBUG] Dialog {dialog.__class__.__name__} accepted but has no 'get_data' method."
                    )
            else:
                print("[DEBUG] Dialog cancelled or closed.")
        else:
            print(f"[DEBUG] Dialog instance was None for {modal_type}.")

    def edit_selected_item(
        self, list_widget: QListWidget, modal_type: str, db_key_str: str
    ):
        """Opens the edit dialog for the item selected in the list widget."""
        print(
            f"[DEBUG] edit_selected_item called for type: {modal_type}, key: {db_key_str}"
        )
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Edit", "Please select an item to edit.")
            return

        # QListWidgetItem から UserRole に格納された ID を取得
        item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        print(f"[DEBUG] Selected item ID: {item_id}")

        # db_key_str を検証し、有効な DatabaseKey か確認
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in STORAGE_KEYS else None  #
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid database key provided: {db_key_str}"
            )
            return

        # db_data からアイテムデータを取得
        item_data = self.db_data.get(db_key, {}).get(item_id)
        if item_data:
            print(f"[DEBUG] Found item data, calling open_edit_dialog...")
            self.open_edit_dialog(modal_type, item_data)  # 編集ダイアログを開く
        else:
            QMessageBox.warning(
                self, "Edit", f"Item data not found for ID '{item_id}' in '{db_key}'."
            )
            print(f"[DEBUG] Item data not found for ID '{item_id}' in '{db_key}'.")

    def delete_selected_item(self, list_widget: QListWidget, db_key_str: str):
        """Deletes the item selected in the list widget."""
        print(f"[DEBUG] delete_selected_item called for key: {db_key_str}")
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Delete", "Please select an item to delete.")
            return

        item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        print(f"[DEBUG] Selected item ID for deletion: {item_id}")

        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in STORAGE_KEYS else None  #
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid database key provided: {db_key_str}"
            )
            return

        # アイテム名を取得して確認メッセージ表示
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        item_name = (
            getattr(item_to_delete, "name", item_id) if item_to_delete else item_id
        )
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"'{item_name}' ({item_id}) を削除しますか？\nこの操作はメモリ上のデータのみに影響し、元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            # メモリ上のデータを削除
            self.handleDeletePart(db_key, item_id)

            # handleDeletePart で実際に削除されたか確認
            if item_id not in self.db_data.get(db_key, {}):
                print(
                    f"[DEBUG] Item {item_id} confirmed deleted from db_data. Removing from list widget."
                )
                # リストウィジェットからもアイテムを削除
                list_widget.takeItem(list_widget.row(selected_items[0]))
                # シーンが削除された場合、関連UIを更新
                if db_key == "scenes":
                    print("[DEBUG] Scene deleted, updating scene combo.")
                    self.update_ui_after_data_change()  # UI全体更新
            else:
                print(
                    f"[DEBUG] Item {item_id} deletion failed or cancelled (handleDeletePart did not remove it)."
                )
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")


# --- Style Definitions (変更なし) ---
buttonStyle: Dict[str, Any] = {
    "padding": "10px",
    "color": "white",
    "border": "none",
    "cursor": "pointer",
    "fontSize": "14px",
    "borderRadius": "4px",
    "lineHeight": "1.5",
}


def buttonGridStyle(columns: int) -> Dict[str, Any]:
    return {
        "display": "grid",
        "gridTemplateColumns": f"repeat({columns}, 1fr)",
        "gap": "10px",
    }


sectionStyle: Dict[str, Any] = {
    "marginBottom": "15px",
    "paddingBottom": "15px",
    "borderBottom": "2px solid #eee",
}
tinyButtonStyle: Dict[str, Any] = {
    "fontSize": "10px",
    "padding": "2px 4px",
    "margin": "0 2px",
}
libraryListStyle: Dict[str, Any] = {
    "maxHeight": "150px",
    "overflowY": "auto",
    "border": "1px solid #eee",
    "marginTop": "5px",
    "padding": "5px",
}
libraryItemStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "padding": "3px 0",
    "borderBottom": "1px solid #f9f9f9",
}
promptAreaStyle: Dict[str, Any] = {
    "width": "95%",
    "fontSize": "0.9em",
    "padding": "4px",
    "margin": "2px 0 5px 0",
    "display": "block",
    "boxSizing": "border-box",
}
sdParamRowStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "alignItems": "center",
    "margin": "3px 0",
}
sdInputStyle: Dict[str, Any] = {"width": "60%"}
directionItemStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "padding": "2px 4px",
    "fontSize": "0.9em",
    "backgroundColor": "#f9f9f9",
    "margin": "2px 0",
    "borderRadius": "3px",
}

# (メイン実行部分は main.py にあるため、ここでは不要)
