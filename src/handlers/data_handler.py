# src/handlers/data_handler.py
import json
import os
from PySide6.QtWidgets import QFileDialog, QMessageBox
from typing import Dict, Optional, Any, Tuple, TYPE_CHECKING
from .. import database as db
from ..models import (
    Work,
    Character,
    Actor,
    Scene,
    Direction,
    Costume,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    Style,
    StableDiffusionParams,
    SceneRole,
    RoleDirection,
    Cut,  # ★ Cut をインポート
    STORAGE_KEYS,
    DatabaseKey,
    ColorPaletteItem,  # ★ Costume インポート用
)

if TYPE_CHECKING:
    from ..main_window import MainWindow  # 型ヒント用にMainWindowをインポート

_CONFIG_FILE_NAME = "config.json"
_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
_CONFIG_FILE_PATH = os.path.join(_DATA_DIR, _CONFIG_FILE_NAME)


class DataHandler:
    def __init__(self, main_window: "MainWindow"):
        self.main_window = main_window  # MainWindowのインスタンスを保持

    def load_config(
        self,
    ) -> Tuple[Optional[str], Optional[str], Dict[str, str], Optional[str]]:
        """設定ファイルから最後の Scene ID, Style ID, 配役, SD Param ID を読み込みます。"""
        default_scene_id = None
        default_style_id = None
        default_assignments = {}
        default_sd_param_id = None  # ★ 追加
        if not os.path.exists(_CONFIG_FILE_PATH):
            print(
                f"[DEBUG] Config file not found: {_CONFIG_FILE_PATH}. Using defaults."
            )
            return (
                default_scene_id,
                default_style_id,
                default_assignments,
                default_sd_param_id,
            )

        try:
            with open(_CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            # 型チェックを追加して安全に取得
            scene_id = (
                config_data.get("last_scene_id")
                if isinstance(config_data.get("last_scene_id"), str)
                else default_scene_id
            )
            style_id = (
                config_data.get("last_style_id")
                if isinstance(config_data.get("last_style_id"), str)
                else default_style_id
            )
            assignments = (
                config_data.get("last_assignments")
                if isinstance(config_data.get("last_assignments"), dict)
                else default_assignments
            )
            sd_param_id = (  # ★ 追加
                config_data.get("last_sd_param_id")
                if isinstance(config_data.get("last_sd_param_id"), str)
                else default_sd_param_id
            )

            print(
                f"[DEBUG] Config loaded: scene={scene_id}, style={style_id}, sd_param={sd_param_id}, assignments={assignments}"
            )
            return scene_id, style_id, assignments, sd_param_id  # ★ 追加
        except (json.JSONDecodeError, OSError, TypeError) as e:
            print(
                f"[ERROR] Failed to load config file {_CONFIG_FILE_PATH}: {e}. Using defaults."
            )
            return (
                default_scene_id,
                default_style_id,
                default_assignments,
                default_sd_param_id,
            )

    def save_config(
        self,
        scene_id: Optional[str],
        style_id: Optional[str],
        assignments: Dict[str, str],
        sd_param_id: Optional[str],  # ★ 追加
    ):
        """現在の Scene ID, Style ID, 配役, SD Param ID を設定ファイルに保存します。"""
        config_data = {
            "last_scene_id": scene_id,
            "last_style_id": style_id,
            "last_assignments": assignments,
            "last_sd_param_id": sd_param_id,  # ★ 追加
        }
        try:
            # data ディレクトリが存在しない場合は作成
            os.makedirs(_DATA_DIR, exist_ok=True)
            with open(_CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"[DEBUG] Config saved to {_CONFIG_FILE_PATH}")
        except (OSError, TypeError) as e:
            print(f"[ERROR] Failed to save config file {_CONFIG_FILE_PATH}: {e}")
            # 保存失敗は警告に留め、アプリの動作は継続
            # QMessageBox.warning(self.main_window, "Config Save Error", f"設定の保存に失敗しました: {e}")

    def load_all_data(
        self,
    ) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
        """データベースから全てのデータをロードします。"""
        print("[DEBUG] DataHandler.load_all_data called.")
        db_data: Dict[str, Dict[str, Any]] = {}
        # sd_params = StableDiffusionParams() # ← 削除
        initial_scene_id: Optional[str] = None
        try:
            db_data["works"] = db.load_works()
            db_data["characters"] = db.load_characters()
            db_data["actors"] = db.load_actors()
            db_data["cuts"] = db.load_cuts()  # ★ Cut 読み込み
            db_data["scenes"] = db.load_scenes()  # Scene は Cut の後に読み込む
            db_data["directions"] = db.load_directions()
            db_data["costumes"] = db.load_costumes()
            db_data["poses"] = db.load_poses()
            db_data["expressions"] = db.load_expressions()
            db_data["backgrounds"] = db.load_backgrounds()
            db_data["lighting"] = db.load_lighting()
            db_data["compositions"] = db.load_compositions()
            db_data["styles"] = db.load_styles()
            db_data["sdParams"] = db.load_sd_params()  # ★ 辞書としてロード
            print("[DEBUG] Data loaded successfully from database.")

            scenes_dict = db_data.get("scenes", {})
            if scenes_dict:
                initial_scene_id = next(iter(scenes_dict), None)
            print(f"[DEBUG] Initial scene ID set to: {initial_scene_id}")

        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Load Error", f"Failed to load data: {e}"
            )
            print(f"[DEBUG] DB load error: {e}")
            db_data = {k: {} for k in STORAGE_KEYS}  # sdParams も辞書として初期化
            initial_scene_id = None

        return db_data, initial_scene_id  # ★ sd_params を返さない

    def save_all_data(
        self,
        db_data: Dict[str, Dict[str, Any]],  # ★ sd_params 引数を削除
    ):
        """メモリ上の全データをSQLiteデータベースに保存します。"""
        print("[DEBUG] DataHandler.save_all_data called.")
        try:
            # 各カテゴリのデータを保存
            for work in db_data.get("works", {}).values():
                db.save_work(work)
            for character in db_data.get("characters", {}).values():
                db.save_character(character)
            for actor in db_data.get("actors", {}).values():
                db.save_actor(actor)
            for cut in db_data.get("cuts", {}).values():
                db.save_cut(cut)  # ★ Cut
            for scene in db_data.get("scenes", {}).values():
                db.save_scene(scene)
            for direction in db_data.get("directions", {}).values():
                db.save_direction(direction)
            for costume in db_data.get("costumes", {}).values():
                db.save_costume(costume)
            for pose in db_data.get("poses", {}).values():
                db.save_pose(pose)
            for expression in db_data.get("expressions", {}).values():
                db.save_expression(expression)
            for background in db_data.get("backgrounds", {}).values():
                db.save_background(background)
            for lighting in db_data.get("lighting", {}).values():
                db.save_lighting(lighting)
            for composition in db_data.get("compositions", {}).values():
                db.save_composition(composition)
            for style in db_data.get("styles", {}).values():
                db.save_style(style)
            # ★ sdParams もループで保存
            for param in db_data.get("sdParams", {}).values():
                db.save_sd_param(param)
            # db.save_sd_params(sd_params) # ← 削除

            QMessageBox.information(
                self.main_window, "Save Data", "全データをデータベースに保存しました。"
            )
            print("[DEBUG] All data saved to database.")
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Save Error",
                f"データベースへの保存中にエラーが発生しました: {e}",
            )
            print(f"[DEBUG] Error saving data to DB: {e}")

    def export_data(
        self,
        db_data: Dict[str, Dict[str, Any]],  # ★ sd_params 引数を削除
    ):
        """現在のデータをJSONファイルにエクスポートします。"""
        print("[DEBUG] DataHandler.export_data called.")
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Export Data to JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
            options=options,
        )
        if fileName:
            if not fileName.endswith(".json"):
                fileName += ".json"
            try:
                export_dict = {}
                for key, data_dict in db_data.items():
                    # sdParams も含め、すべての dataclass ベースの辞書をエクスポート
                    export_dict[key] = {
                        item_id: item.__dict__ for item_id, item in data_dict.items()
                    }
                # export_dict["sdParams"] = sd_params.__dict__ # ← 削除

                # ネストされた dataclass リストを辞書に変換
                if "scenes" in export_dict:
                    for scene_id, scene_data in export_dict["scenes"].items():
                        # Scene.cuts は ID リストになったので変換不要
                        scene_data.pop("cuts", None)  # cuts 属性はもうない
                        scene_data["role_directions"] = [
                            rd.__dict__ for rd in scene_data.get("role_directions", [])
                        ]
                if "cuts" in export_dict:
                    for cut_id, cut_data in export_dict["cuts"].items():
                        cut_data["roles"] = [
                            r.__dict__ for r in cut_data.get("roles", [])
                        ]
                if "costumes" in export_dict:
                    for costume_id, costume_data in export_dict["costumes"].items():
                        # color_ref は既に文字列なのでそのまま
                        costume_data["color_palette"] = [
                            cp.__dict__ for cp in costume_data.get("color_palette", [])
                        ]

                with open(fileName, "w", encoding="utf-8") as f:
                    json.dump(export_dict, f, indent=2, ensure_ascii=False)
                QMessageBox.information(
                    self.main_window,
                    "Export Success",
                    f"データを {fileName} にエクスポートしました。",
                )
                print(f"[DEBUG] Data exported to {fileName}")
            except Exception as e:
                QMessageBox.critical(
                    self.main_window,
                    "Export Error",
                    f"JSONファイルへのエクスポート中にエラーが発生しました: {e}",
                )
                print(f"[DEBUG] Error exporting data: {e}")

    def import_data(
        self,
    ) -> Optional[Dict[str, Dict[str, Any]]]:  # ★ 戻り値を変更
        """JSONファイルからデータをインポートし、新しいデータセットを返します。"""
        print("[DEBUG] DataHandler.import_data called.")
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Import Data from JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
            options=options,
        )
        if fileName:
            confirm = QMessageBox.question(
                self.main_window,
                "Confirm Import",
                "現在のメモリ上のデータをJSONファイルの内容で上書きしますか？\n(データベースには保存されません。保存するにはSave to DBを押してください)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    with open(fileName, "r", encoding="utf-8") as f:
                        imported_data = json.load(f)

                    new_db_data: Dict[str, Dict[str, Any]] = {}
                    # new_sd_params = StableDiffusionParams() # ← 削除
                    type_map = {
                        "works": Work,
                        "characters": Character,
                        "actors": Actor,
                        "cuts": Cut,
                        "scenes": Scene,
                        "directions": Direction,
                        "costumes": Costume,
                        "poses": Pose,
                        "expressions": Expression,
                        "backgrounds": Background,
                        "lighting": Lighting,
                        "compositions": Composition,
                        "styles": Style,
                        "sdParams": StableDiffusionParams,  # ★ sdParams を追加
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
                                # ネストされた dataclass の復元
                                if klass == Scene:
                                    # Scene.cuts は ID リストのはず
                                    item_data.pop(
                                        "cuts", None
                                    )  # 旧データの cuts リストは削除
                                    item_data["role_directions"] = [
                                        RoleDirection(**rd)
                                        for rd in item_data.get("role_directions", [])
                                    ]
                                elif klass == Cut:
                                    item_data["roles"] = [
                                        SceneRole(**r)
                                        for r in item_data.get("roles", [])
                                    ]
                                elif klass == Costume:
                                    # color_ref は文字列として読み込まれる
                                    item_data["color_palette"] = [
                                        ColorPaletteItem(**cp)
                                        for cp in item_data.get("color_palette", [])
                                    ]

                                new_db_data[key][item_id] = klass(**item_data)
                            except Exception as ex:
                                print(
                                    f"[DEBUG] Import Warning: Skipping item '{item_id}' in '{key}' due to error: {ex}. Data: {item_data}"
                                )

                    # sdParams の特別な処理は不要になった

                    QMessageBox.information(
                        self.main_window,
                        "Import Success",
                        f"データを {fileName} からメモリにインポートしました。\n変更を永続化するには 'Save to DB' を押してください。",
                    )
                    print(f"[DEBUG] Data imported from {fileName} into memory.")
                    return new_db_data  # ★ new_db_data のみを返す

                except Exception as e:
                    QMessageBox.critical(
                        self.main_window,
                        "Import Error",
                        f"データのインポート中にエラーが発生しました: {e}",
                    )
                    print(f"[DEBUG] Error importing data: {e}")
        return None

    def save_single_item(self, db_key: DatabaseKey, item_data: Any):
        """指定されたタイプの単一アイテムをデータベースに保存します。"""
        print(
            f"[DEBUG] DataHandler.save_single_item called for {db_key} - {getattr(item_data, 'id', 'N/A')}"
        )
        try:
            if db_key == "works" and isinstance(item_data, Work):
                db.save_work(item_data)
            elif db_key == "characters" and isinstance(item_data, Character):
                db.save_character(item_data)
            elif db_key == "actors" and isinstance(item_data, Actor):
                db.save_actor(item_data)
            elif db_key == "cuts" and isinstance(item_data, Cut):
                db.save_cut(item_data)
            elif db_key == "scenes" and isinstance(item_data, Scene):
                db.save_scene(item_data)
            elif db_key == "directions" and isinstance(item_data, Direction):
                db.save_direction(item_data)
            elif db_key == "costumes" and isinstance(item_data, Costume):
                db.save_costume(item_data)
            elif db_key == "poses" and isinstance(item_data, Pose):
                db.save_pose(item_data)
            elif db_key == "expressions" and isinstance(item_data, Expression):
                db.save_expression(item_data)
            elif db_key == "backgrounds" and isinstance(item_data, Background):
                db.save_background(item_data)
            elif db_key == "lighting" and isinstance(item_data, Lighting):
                db.save_lighting(item_data)
            elif db_key == "compositions" and isinstance(item_data, Composition):
                db.save_composition(item_data)
            elif db_key == "styles" and isinstance(item_data, Style):
                db.save_style(item_data)
            elif db_key == "sdParams" and isinstance(item_data, StableDiffusionParams):
                db.save_sd_param(item_data)  # ★ 修正
            else:
                print(
                    f"[DEBUG] Warning: save_single_item - Unsupported db_key '{db_key}' or incorrect data type '{type(item_data).__name__}'."
                )
                return

            print(
                f"[DEBUG] Successfully saved item {getattr(item_data, 'id', 'N/A')} to DB table '{db_key}'."
            )

        except Exception as e:
            QMessageBox.warning(
                self.main_window,
                "DB Save Warning",
                f"Failed to save new item {getattr(item_data, 'id', 'N/A')} to database immediately: {e}",
            )
            print(f"[DEBUG] Error in save_single_item for {db_key}: {e}")
            import traceback

            traceback.print_exc()

    def handle_delete_part(
        self, db_key: DatabaseKey, partId: str, db_data: Dict[str, Dict[str, Any]]
    ) -> bool:
        """メモリ上のデータを削除します (MainWindow から呼び出される)。"""
        item_to_delete = db_data.get(db_key, {}).get(partId)
        partName = getattr(item_to_delete, "name", "Item") if item_to_delete else "Item"
        print(
            f"[DEBUG] DataHandler.handle_delete_part called for db_key='{db_key}', partId='{partId}' ({partName})"
        )

        if db_key in db_data and partId in db_data[db_key]:
            del db_data[db_key][partId]
            print(f"[DEBUG] Deletion from db_data complete for {partId}.")
            return True
        else:
            print(f"[DEBUG] Item {partId} not found in {db_key}, cannot delete.")
            return False
