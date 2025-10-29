# src/handlers/data_handler.py
import json
import os
import time
import traceback
from PySide6.QtWidgets import QFileDialog, QMessageBox
from typing import Dict, Optional, Any, Tuple, TYPE_CHECKING, List
from .. import database as db
from ..models import (
    Work,
    Character,
    Actor,
    Scene,
    Costume,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    Style,
    StableDiffusionParams,
    SceneRole,
    Cut,
    Sequence,
    SequenceSceneEntry,
    QueueItem,
    STORAGE_KEYS,
    DatabaseKey,
    ColorPaletteItem,
    State,
    AdditionalPrompt,
    RoleAppearanceAssignment,
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

    def load_config(self) -> Tuple[Optional[str], Dict[str, str]]:  # ★ 戻り値変更
        """設定ファイルから最後の Scene ID, 配役を読み込みます。"""
        default_scene_id = None
        default_assignments = {}
        # default_style_id = None # ← 削除
        # default_sd_param_id = None # ← 削除

        if not os.path.exists(_CONFIG_FILE_PATH):
            print(
                f"[DEBUG] Config file not found: {_CONFIG_FILE_PATH}. Using defaults."
            )
            return default_scene_id, default_assignments  # ★ 戻り値変更

        try:
            with open(_CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            scene_id = (
                config_data.get("last_scene_id")
                if isinstance(config_data.get("last_scene_id"), str)
                else default_scene_id
            )
            assignments = (
                config_data.get("last_assignments")
                if isinstance(config_data.get("last_assignments"), dict)
                else default_assignments
            )
            # style_id = ... # ← 削除
            # sd_param_id = ... # ← 削除

            print(f"[DEBUG] Config loaded: scene={scene_id}, assignments={assignments}")
            return scene_id, assignments  # ★ 戻り値変更
        except (json.JSONDecodeError, OSError, TypeError) as e:
            print(
                f"[ERROR] Failed to load config file {_CONFIG_FILE_PATH}: {e}. Using defaults."
            )
            return default_scene_id, default_assignments  # ★ 戻り値変更

    def save_config(
        self, scene_id: Optional[str], assignments: Dict[str, str]
    ):  # ★ 引数変更
        """現在の Scene ID, 配役を設定ファイルに保存します。"""
        config_data = {
            "last_scene_id": scene_id,
            "last_assignments": assignments,
            # "last_style_id": style_id, # ← 削除
            # "last_sd_param_id": sd_param_id, # ← 削除
        }
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            with open(_CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"[DEBUG] Config saved to {_CONFIG_FILE_PATH}")
        except (OSError, TypeError) as e:
            print(f"[ERROR] Failed to save config file {_CONFIG_FILE_PATH}: {e}")

    def load_all_data(
        self,
    ) -> Tuple[
        Dict[str, Dict[str, Any]], List[QueueItem], Optional[str]
    ]:  # ★ 戻り値の型を修正
        """データベースから全てのデータをロードします。"""
        print("[DEBUG] DataHandler.load_all_data called.")
        db_data: Dict[str, Dict[str, Any]] = {}
        batch_queue: List[QueueItem] = []
        initial_scene_id: Optional[str] = None
        try:
            db_data["works"] = db.load_works()
            db_data["characters"] = db.load_characters()
            db_data["actors"] = db.load_actors()
            db_data["cuts"] = db.load_cuts()
            db_data["scenes"] = db.load_scenes()
            db_data["costumes"] = db.load_costumes()
            db_data["poses"] = db.load_poses()
            db_data["expressions"] = db.load_expressions()
            db_data["backgrounds"] = db.load_backgrounds()
            db_data["lighting"] = db.load_lighting()
            db_data["compositions"] = db.load_compositions()
            db_data["styles"] = db.load_styles()
            db_data["sdParams"] = db.load_sd_params()
            db_data["sequences"] = db.load_sequences()
            db_data["states"] = db.load_states()
            db_data["additional_prompts"] = db.load_additional_prompts()  # ★ 追加
            batch_queue = db.load_batch_queue()

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
            db_data = {k: {} for k in STORAGE_KEYS}
            batch_queue = []
            initial_scene_id = None

        return db_data, batch_queue, initial_scene_id  # ★ 戻り値を修正

    def save_all_data(
        self,
        db_data: Dict[str, Dict[str, Any]],
        batch_queue: List[QueueItem],  # ★ batch_queue を引数に追加
    ):
        """メモリ上の全データをSQLiteデータベースに保存します。"""
        print("[DEBUG] DataHandler.save_all_data called.")
        try:
            for work in db_data.get("works", {}).values():
                db.save_work(work)
            for character in db_data.get("characters", {}).values():
                db.save_character(character)
            for actor in db_data.get("actors", {}).values():
                db.save_actor(actor)
            for cut in db_data.get("cuts", {}).values():
                db.save_cut(cut)
            for scene in db_data.get("scenes", {}).values():
                db.save_scene(scene)
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
            for param in db_data.get("sdParams", {}).values():
                db.save_sd_param(param)
            for sequence in db_data.get("sequences", {}).values():
                db.save_sequence(sequence)
            for state in db_data.get("states", {}).values():
                db.save_state(state)
            for ap in db_data.get("additional_prompts", {}).values():
                db.save_additional_prompt(ap)  # ★ 追加

            db.clear_batch_queue()
            for item in batch_queue:
                db.save_queue_item(item)

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
        self, db_data: Dict[str, Dict[str, Any]], batch_queue: List[QueueItem]
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
                # ★ db_data 全体をエクスポート
                for key, data_dict in db_data.items():
                    export_dict[key] = {
                        item_id: item.__dict__ for item_id, item in data_dict.items()
                    }

                # ネストされた dataclass リストを辞書に変換
                if "scenes" in export_dict:
                    for scene_id, scene_data in export_dict["scenes"].items():
                        # role_directions -> role_assignments
                        scene_data["role_assignments"] = [
                            ra.__dict__ for ra in scene_data.get("role_assignments", [])
                        ]
                if "cuts" in export_dict:
                    for cut_id, cut_data in export_dict["cuts"].items():
                        cut_data["roles"] = [
                            r.__dict__ for r in cut_data.get("roles", [])
                        ]
                if "costumes" in export_dict:
                    for costume_id, costume_data in export_dict["costumes"].items():
                        costume_data["color_palette"] = [
                            cp.__dict__ for cp in costume_data.get("color_palette", [])
                        ]
                if (
                    "sequences" in export_dict
                ):  # ★ db_data から取得したので db_data["sequences"] ではなく export_dict
                    for seq_id, seq_data in export_dict["sequences"].items():
                        seq_dict = seq_data  # 既に __dict__ 済み
                        seq_dict["scene_entries"] = [
                            entry.__dict__
                            for entry in seq_data.get("scene_entries", [])
                        ]
                        # export_dict["sequences"][seq_id] = seq_dict # 辞書を上書きしない

                export_dict["batch_queue"] = [item.__dict__ for item in batch_queue]

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
    ) -> Optional[Tuple[Dict[str, Dict[str, Any]], List[QueueItem]]]:
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
                    new_batch_queue: List[QueueItem] = []
                    type_map = {
                        "works": Work,
                        "characters": Character,
                        "actors": Actor,
                        "cuts": Cut,
                        "scenes": Scene,
                        "costumes": Costume,
                        "poses": Pose,
                        "expressions": Expression,
                        "backgrounds": Background,
                        "lighting": Lighting,
                        "compositions": Composition,
                        "styles": Style,
                        "sdParams": StableDiffusionParams,
                        "sequences": Sequence,
                        "states": State,
                        "additional_prompts": AdditionalPrompt,  # ★ 追加
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
                                    # role_directions -> role_assignments
                                    item_data["role_assignments"] = [
                                        RoleAppearanceAssignment(**ra)
                                        for ra in item_data.get("role_assignments", [])
                                    ]
                                    # 古い role_directions があれば削除
                                    item_data.pop("role_directions", None)
                                elif klass == Cut:
                                    item_data["roles"] = [
                                        SceneRole(**r)
                                        for r in item_data.get("roles", [])
                                    ]
                                elif klass == Costume:
                                    item_data["color_palette"] = [
                                        ColorPaletteItem(**cp)
                                        for cp in item_data.get("color_palette", [])
                                    ]
                                elif klass == Sequence:
                                    item_data["scene_entries"] = [
                                        SequenceSceneEntry(**entry)
                                        for entry in item_data.get("scene_entries", [])
                                    ]

                                new_db_data[key][item_id] = klass(**item_data)
                            except Exception as ex:
                                print(
                                    f"[DEBUG] Import Warning: Skipping item '{item_id}' in '{key}' due to error: {ex}. Data: {item_data}"
                                )

                    # ★ Batch Queue の復元 (変更なし)
                    queue_list = imported_data.get("batch_queue", [])
                    if isinstance(queue_list, list):
                        for item_data in queue_list:
                            try:
                                if "order" not in item_data:
                                    item_data["order"] = 0
                                if "id" not in item_data or not item_data["id"]:
                                    item_data["id"] = (
                                        f"queue_item_{int(time.time() * 1000)}_{len(new_batch_queue)}"
                                    )
                                new_batch_queue.append(QueueItem(**item_data))
                            except Exception as ex:
                                print(
                                    f"[DEBUG] Import Warning: Skipping queue item due to error: {ex}. Data: {item_data}"
                                )
                    new_batch_queue.sort(key=lambda item: item.order)
                    for i, item in enumerate(new_batch_queue):
                        item.order = i

                    QMessageBox.information(
                        self.main_window,
                        "Import Success",
                        f"データを {fileName} からメモリにインポートしました。\n変更を永続化するには 'Save to DB' を押してください。",
                    )
                    print(f"[DEBUG] Data imported from {fileName} into memory.")
                    return new_db_data, new_batch_queue

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
            elif db_key == "sequences" and isinstance(item_data, Sequence):
                db.save_sequence(item_data)
            elif db_key == "states" and isinstance(item_data, State):
                db.save_state(item_data)
            elif db_key == "additional_prompts":
                db.save_additional_prompt(item_data)
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
        self,
        db_key: DatabaseKey,
        partId: str,
        db_data: Dict[str, Dict[str, Any]],
        batch_queue: List[QueueItem],
    ) -> Tuple[bool, bool]:
        """メモリ上のデータを削除します。キュー内の関連アイテムも削除します。"""
        print(
            f"[DEBUG] DataHandler.handle_delete_part called for db_key='{db_key}', partId='{partId}'..."
        )

        queue_modified = False
        deleted_from_memory = False

        if db_key in db_data and partId in db_data[db_key]:
            del db_data[db_key][partId]
            deleted_from_memory = True
            print(f"[DEBUG] Deletion from db_data complete for {partId}.")

            if db_key == "sequences":
                original_queue_len = len(batch_queue)
                new_queue = [item for item in batch_queue if item.sequence_id != partId]
                if len(new_queue) < original_queue_len:
                    queue_modified = True
                    print(
                        f"[DEBUG] Removed queue items associated with deleted sequence {partId}."
                    )
                    for i, item in enumerate(new_queue):
                        item.order = i
                    batch_queue[:] = new_queue

            if db_key == "states":
                for costume in db_data.get("costumes", {}).values():
                    if hasattr(costume, "state_ids") and partId in costume.state_ids:
                        costume.state_ids.remove(partId)
                        print(
                            f"[DEBUG] Removed deleted state ID {partId} from costume {costume.id}"
                        )

            # --- ▼▼▼ Scene から Additional Prompt ID 削除 ▼▼▼ ---
            if db_key == "additional_prompts":
                for scene in db_data.get("scenes", {}).values():
                    if (
                        hasattr(scene, "additional_prompt_ids")
                        and partId in scene.additional_prompt_ids
                    ):
                        scene.additional_prompt_ids.remove(partId)
                        print(
                            f"[DEBUG] Removed deleted AP ID {partId} from scene {scene.id}"
                        )
            if db_key in ["costumes", "poses", "expressions"]:
                id_list_name = f"{db_key}_ids"  # costumes -> costume_ids
                for scene in db_data.get("scenes", {}).values():
                    if hasattr(scene, "role_assignments"):
                        for ra in scene.role_assignments:
                            if hasattr(ra, id_list_name) and partId in getattr(
                                ra, id_list_name
                            ):
                                getattr(ra, id_list_name).remove(partId)
                                print(
                                    f"[DEBUG] Removed deleted {db_key} ID {partId} from scene {scene.id}, role {ra.role_id}"
                                )
            # --- ▲▲▲ 追加 ▲▲▲ ---

        else:
            print(f"[DEBUG] Item {partId} not found in {db_key}, cannot delete.")

        return deleted_from_memory, queue_modified

    # --- ▼▼▼ キュー操作用メソッドを追加 ▼▼▼ ---
    def save_batch_queue(self, batch_queue: List[QueueItem]):
        """現在のキューの状態をDBに保存します。"""
        try:
            db.clear_batch_queue()
            for item in batch_queue:
                db.save_queue_item(item)
            print("[DEBUG] Batch queue saved to database.")
        except Exception as e:
            QMessageBox.warning(
                self.main_window, "Queue Save Error", f"キューの保存に失敗しました: {e}"
            )
            print(f"[ERROR] Failed to save batch queue: {e}")

    def add_item_to_queue(
        self,
        sequence_id: str,
        actor_assignments: Dict[str, str],
        batch_queue: List[QueueItem],
    ):
        """新しいアイテムをキューの末尾に追加し、DBに保存します。"""
        new_order = len(batch_queue)
        new_item = QueueItem(
            id=f"queue_item_{int(time.time() * 1000)}_{new_order}",
            sequence_id=sequence_id,
            actor_assignments=actor_assignments,
            order=new_order,
        )
        batch_queue.append(new_item)
        self.save_batch_queue(batch_queue)  # DBにも保存

    def update_queue_item_assignments(
        self,
        item_id: str,
        new_assignments: Dict[str, str],
        batch_queue: List[QueueItem],
    ):
        """指定されたキューアイテムのアクター割り当てを更新し、DBに保存します。"""
        item_updated = False
        for item in batch_queue:
            if item.id == item_id:
                item.actor_assignments = new_assignments
                item_updated = True
                break
        if item_updated:
            self.save_batch_queue(batch_queue)
        else:
            print(
                f"[WARN] Could not find queue item with id {item_id} to update assignments."
            )

    def remove_item_from_queue(
        self, item_id: str, batch_queue: List[QueueItem]
    ) -> bool:
        """指定されたアイテムをキューから削除し、DBを更新、order を再割り当てします。"""
        original_len = len(batch_queue)
        new_queue = [item for item in batch_queue if item.id != item_id]
        if len(new_queue) < original_len:
            # order を再割り当て
            for i, item in enumerate(new_queue):
                item.order = i
            batch_queue[:] = new_queue  # リストを更新
            self.save_batch_queue(batch_queue)  # DBも更新
            return True
        return False

    def reorder_queue(self, new_ordered_ids: List[str], batch_queue: List[QueueItem]):
        """キューの順序を更新し、DBに保存します。"""
        id_to_item = {item.id: item for item in batch_queue}
        new_queue = []
        for i, item_id in enumerate(new_ordered_ids):
            item = id_to_item.get(item_id)
            if item:
                item.order = i
                new_queue.append(item)
            else:
                print(f"[WARN] Item ID {item_id} not found during reorder.")

        if len(new_queue) == len(batch_queue):  # 整合性チェック
            batch_queue[:] = new_queue
            self.save_batch_queue(batch_queue)
        else:
            QMessageBox.warning(
                self.main_window,
                "Queue Reorder Error",
                "キューの並び替え中に不整合が発生しました。",
            )
