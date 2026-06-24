# src/database.py
import sqlite3
import json
import os
from typing import Dict, List, Type, TypeVar, Any

T = TypeVar("T")  # ジェネリック型

# モデルとヘルパー関数をインポート
from .models import (
    Work,
    Character,
    Actor,
    StateCategory,
    Scene,
    Costume,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    StableDiffusionParams,
    Cut,
    SceneRole,
    Style,
    ColorPaletteItem,
    Sequence,
    SequenceSceneEntry,
    QueueItem,
    State,
    AdditionalPrompt,
    RoleAppearanceAssignment,
)
from .utils.json_helpers import (
    list_to_json_str,
    json_str_to_list,
    dataclass_list_to_json_str,
    json_str_to_dataclass_list,
    dict_to_json_str,
    json_str_to_dict,  # ★ dict用ヘルパー追加
)

# 初期データをインポート
from .data.mocks import initialMockDatabase

# --- 定数定義 ---
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB_PATH は直接使わず、get_db_path() を介して取得する
_db_path = None


def set_db_path(path: str):
    """データベースへのパスを設定します。"""
    global _db_path
    _db_path = path
    # パスが設定されたら、ディレクトリが存在することを確認
    os.makedirs(os.path.dirname(path), exist_ok=True)


def get_db_path() -> str:
    """現在設定されているデータベースのパスを取得します。"""
    if not _db_path:
        # デフォルトパスを構築
        return os.path.join(_BASE_DIR, "..", "data", "prompt_data.db")
    return _db_path


# --- データベース接続 ---
def get_connection():
    """データベース接続を取得します。"""
    path = get_db_path()
    if not path:
        raise ValueError("データベースパスが設定されていません。set_db_path()を呼び出してください。")
    return sqlite3.connect(path)


# --- データベース初期化 ---
def _add_created_at_if_not_exists(cursor: sqlite3.Cursor, table_name: str):
    """テーブルに created_at カラムがなければ追加するヘルパー関数"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        if "created_at" not in columns:
            print(f"[INFO] Migrating '{table_name}' table: Adding 'created_at' column.")
            # time.time() のような float を格納するため REAL を使用
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN created_at REAL DEFAULT 0")
            print(f"[INFO] 'created_at' column added to '{table_name}' successfully.")
    except sqlite3.Error as e:
        print(f"[WARN] An error occurred during schema migration for '{table_name}': {e}")


def _add_column_if_not_exists(
    cursor: sqlite3.Cursor, table_name: str, column_name: str, column_def: str
):
    """テーブルに指定カラムがなければ追加するヘルパー関数"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        if column_name not in columns:
            print(
                f"[INFO] Migrating '{table_name}' table: Adding '{column_name}' column."
            )
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
            )
            print(
                f"[INFO] '{column_name}' column added to '{table_name}' successfully."
            )
    except sqlite3.Error as e:
        print(
            f"[WARN] An error occurred during schema migration for '{table_name}.{column_name}': {e}"
        )


def _ensure_legacy_state_categories(cursor: sqlite3.Cursor):
    """既存の文字列カテゴリ参照から state_categories テーブルを補完する。"""
    try:
        cursor.execute("SELECT id FROM state_categories")
        existing_ids = {row[0] for row in cursor.fetchall()}

        legacy_category_ids = set()

        cursor.execute("SELECT category FROM states")
        for (category_id,) in cursor.fetchall():
            if category_id:
                legacy_category_ids.add(category_id)

        cursor.execute("SELECT state_categories FROM scenes")
        for (raw_categories,) in cursor.fetchall():
            if not raw_categories:
                continue
            try:
                category_ids = json.loads(raw_categories)
            except json.JSONDecodeError:
                category_ids = []
            for category_id in category_ids:
                if category_id:
                    legacy_category_ids.add(category_id)

        for category_id in sorted(legacy_category_ids):
            if category_id not in existing_ids:
                cursor.execute(
                    "INSERT OR REPLACE INTO state_categories (id, name, created_at) VALUES (?, ?, ?)",
                    (category_id, category_id, 0),
                )
    except sqlite3.Error as e:
        print(f"[WARN] Failed to backfill state categories: {e}")

def initialize_db():
    """
    データベースファイルが存在しない場合は作成し、必要なテーブルが存在しない場合は作成します。
    テーブルが新規に作成された場合のみ、初期データを挿入します。
    """
    db_path = get_db_path()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='works'")
    works_table_existed_before = cursor.fetchone() is not None
    
    try:
        print("[INFO] Ensuring database tables exist...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id TEXT PRIMARY KEY, title_jp TEXT, title_en TEXT,
                title_file_safe_jp TEXT, tags TEXT, sns_tags TEXT, created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, work_id TEXT, tags TEXT,
                personal_color TEXT, underwear_color TEXT, created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt TEXT, negative_prompt TEXT, created_at REAL,
                character_id TEXT,
                base_costume_id TEXT, base_pose_id TEXT, base_expression_id TEXT,
                setting_image_path TEXT
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cuts (
                id TEXT PRIMARY KEY, name TEXT,
                prompt_template TEXT, negative_template TEXT,
                roles TEXT,
                reference_image_path TEXT,
                image_mode TEXT, created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                background_id TEXT, lighting_id TEXT, 
                composition_ids TEXT, 
                cut_id TEXT,
                role_assignments TEXT,
                style_id TEXT,
                sd_param_ids TEXT,
                state_categories TEXT,additional_prompt_ids TEXT,
                reference_image_path TEXT,
                reference_mode TEXT,
                adetailer_enabled INTEGER DEFAULT 0,
                adetailer_models TEXT DEFAULT '[]',
                created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS costumes (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt TEXT, negative_prompt TEXT, created_at REAL,
                color_palette TEXT,
                state_ids TEXT
            )""")

        simple_parts_tables = [
            "poses", "expressions", "backgrounds", "lighting",
            "compositions", "styles", "additional_prompts",
        ]
        for table_name in simple_parts_tables:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                    prompt TEXT, negative_prompt TEXT, created_at REAL
                )""")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS states (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                prompt TEXT,
                negative_prompt TEXT, created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sd_params (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                steps INTEGER, sampler_name TEXT, cfg_scale REAL,
                seed INTEGER, width INTEGER, height INTEGER,
                denoising_strength REAL,
                model TEXT, created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sequences (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                scene_entries TEXT, created_at REAL
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_queue (
                id TEXT PRIMARY KEY,
                sequence_id TEXT NOT NULL,
                actor_assignments TEXT,
                item_order INTEGER,
                appearance_overrides TEXT DEFAULT '{}'
            )""")
        
        print("[INFO] Database tables ensured.")

        # --- スキーママイグレーション ---
        all_tables = [
            "works", "characters", "actors", "cuts", "scenes", "costumes",
            "poses", "expressions", "backgrounds", "lighting", "compositions",
            "styles", "additional_prompts", "states", "state_categories", "sd_params", "sequences"
        ]
        for table in all_tables:
            _add_created_at_if_not_exists(cursor, table)

        _add_column_if_not_exists(cursor, "actors", "setting_image_path", "TEXT DEFAULT ''")
        _add_column_if_not_exists(
            cursor, "scenes", "reference_image_path", "TEXT DEFAULT ''"
        )
        _add_column_if_not_exists(
            cursor, "scenes", "reference_mode", "TEXT DEFAULT 'none'"
        )
        _add_column_if_not_exists(
            cursor, "scenes", "adetailer_enabled", "INTEGER DEFAULT 0"
        )
        _add_column_if_not_exists(
            cursor, "scenes", "adetailer_models", "TEXT DEFAULT '[]'"
        )

        _ensure_legacy_state_categories(cursor)

        try:
            cursor.execute("PRAGMA table_info(sd_params)")
            columns = [column[1] for column in cursor.fetchall()]
            if "model" not in columns:
                print("[INFO] Migrating 'sd_params' table: Adding 'model' column.")
                cursor.execute("ALTER TABLE sd_params ADD COLUMN model TEXT")
                print("[INFO] 'model' column added to 'sd_params' successfully.")
        except sqlite3.Error as e:
            print(f"[WARN] An error occurred during schema migration: {e}")

        try:
            cursor.execute("PRAGMA table_info(works)")
            columns = [column[1] for column in cursor.fetchall()]
            if "title_file_safe_jp" not in columns:
                print("[INFO] Migrating 'works' table: Adding 'title_file_safe_jp' column.")
                cursor.execute("ALTER TABLE works ADD COLUMN title_file_safe_jp TEXT")
                print("[INFO] 'title_file_safe_jp' column added to 'works' successfully.")
        except sqlite3.Error as e:
            print(f"[WARN] An error occurred during schema migration for works: {e}")

        if not works_table_existed_before:
            print(
                "[INFO] Initializing database with mock data as 'works' table was missing..."
            )
            try:
                for work in initialMockDatabase.works.values(): save_work(work)
                for character in initialMockDatabase.characters.values(): save_character(character)
                for actor in initialMockDatabase.actors.values(): save_actor(actor)
                for cut in initialMockDatabase.cuts.values(): save_cut(cut)
                for scene in initialMockDatabase.scenes.values(): save_scene(scene)
                for costume in initialMockDatabase.costumes.values(): save_costume(costume)
                for pose in initialMockDatabase.poses.values(): save_pose(pose)
                for expression in initialMockDatabase.expressions.values(): save_expression(expression)
                for background in initialMockDatabase.backgrounds.values(): save_background(background)
                for lighting in initialMockDatabase.lighting.values(): save_lighting(lighting)
                for composition in initialMockDatabase.compositions.values(): save_composition(composition)
                for style in initialMockDatabase.styles.values(): save_style(style)
                for param in initialMockDatabase.sdParams.values(): save_sd_param(param)
                for category in initialMockDatabase.state_categories.values(): save_state_category(category)
                for state in initialMockDatabase.states.values(): save_state(state)
                for ap in initialMockDatabase.additional_prompts.values(): save_additional_prompt(ap)
                print("[INFO] Initial mock data inserted.")
            except Exception as insert_e:
                print(f"[ERROR] Failed to insert initial data: {insert_e}")
                conn.rollback()
                raise
        else:
            print(
                "[INFO] Database tables already exist. Skipping initial data insertion."
            )
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"データベース初期化中にエラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()
    print(f"データベースの準備が完了しました: {get_db_path()}")


# --- ▲▲▲ 修正ここまで ▲▲▲


# --- Generic Load/Save/Delete Functions ---
def _save_item(table_name: str, item_data: Dict[str, Any]):
    """汎用: アイテムをテーブルに挿入または置換します。"""
    conn = get_connection()
    cursor = conn.cursor()
    columns = ", ".join(item_data.keys())
    placeholders = ", ".join(["?"] * len(item_data))
    sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
    try:
        cursor.execute(sql, list(item_data.values()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving item to {table_name}: {e}")
        conn.rollback()
    finally:
        conn.close()


def _load_items(table_name: str, class_type: Type[T]) -> Dict[str, T]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    items: Dict[str, T] = {}
    try:
        # created_at カラムが存在するかチェック
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        order_by_clause = "ORDER BY created_at DESC" if "created_at" in columns else ""
        
        cursor.execute(f"SELECT * FROM {table_name} {order_by_clause}")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print(f"テーブル '{table_name}' が見つかりません。空の辞書を返します。")
        rows = []
    finally:
        conn.close()
    class_fields = {f.name for f in class_type.__dataclass_fields__.values()}
    for row in rows:
        row_dict_raw = dict(row)
        item_id = row_dict_raw.get("id")
        if not item_id:
            continue

        if table_name == "scenes":
            if "composition_id" in row_dict_raw:
                old_comp_id = row_dict_raw.pop("composition_id", None)
                if old_comp_id and not row_dict_raw.get("composition_ids"):
                    row_dict_raw["composition_ids"] = list_to_json_str([old_comp_id])

            if "sd_param_id" in row_dict_raw:
                old_sd_id = row_dict_raw.pop("sd_param_id", None)
                if old_sd_id and not row_dict_raw.get("sd_param_ids"):
                    row_dict_raw["sd_param_ids"] = list_to_json_str([old_sd_id])

        row_dict = {k: v for k, v in row_dict_raw.items() if k in class_fields}

        # 新しい created_at フィールドが DB にまだなく、None になる場合を考慮
        if "created_at" in class_fields and row_dict.get("created_at") is None:
            row_dict["created_at"] = 0.0 # デフォルト値

        if "tags" in row_dict and isinstance(row_dict["tags"], str):
            try:
                row_dict["tags"] = json.loads(row_dict["tags"])
            except json.JSONDecodeError:
                row_dict["tags"] = []

        if class_type == Scene:
            row_dict["reference_image_path"] = (
                row_dict.get("reference_image_path") or ""
            )
            row_dict["reference_mode"] = row_dict.get("reference_mode") or "none"
            row_dict["adetailer_enabled"] = bool(
                row_dict.get("adetailer_enabled")
            )
            row_dict["adetailer_models"] = json_str_to_list(
                row_dict.get("adetailer_models"), str
            )
            row_dict["state_categories"] = json_str_to_list(
                row_dict.get("state_categories"), str
            )
            row_dict["additional_prompt_ids"] = json_str_to_list(
                row_dict.get("additional_prompt_ids"), str
            )
            row_dict["role_assignments"] = json_str_to_dataclass_list(
                row_dict.get("role_assignments"), RoleAppearanceAssignment
            )
            row_dict["composition_ids"] = json_str_to_list(
                row_dict.get("composition_ids"), str
            )
            row_dict["sd_param_ids"] = json_str_to_list(
                row_dict.get("sd_param_ids"), str
            )  # ★ 追加

        if class_type == Costume:
            row_dict["state_ids"] = json_str_to_list(row_dict.get("state_ids"), str)
            row_dict["color_palette"] = json_str_to_dataclass_list(
                row_dict.get("color_palette"), ColorPaletteItem
            )
        if class_type == Cut:
            row_dict["roles"] = json_str_to_dataclass_list(row_dict.get("roles"), SceneRole)
        if class_type == Sequence:
            row_dict["scene_entries"] = json_str_to_dataclass_list(
                row_dict.get("scene_entries"), SequenceSceneEntry
            )

        try:
            items[item_id] = class_type(**row_dict)
        except Exception as e:
            print(
                f"Error creating instance of {class_type.__name__} for id '{item_id}'. Data: {row_dict}. Error: {e}"
            )
            import traceback

            traceback.print_exc()
    return items


def _delete_item(table_name: str, item_id: str):
    """汎用: 指定されたIDのアイテムを削除します。"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error deleting item {item_id} from {table_name}: {e}")
        conn.rollback()
    finally:
        conn.close()


# --- Specific Save/Load/Delete Functions ---


# --- Cut ---
def save_cut(cut: Cut):
    data = cut.__dict__.copy()
    data["roles"] = list_to_json_str(data.get("roles", []))
    _save_item("cuts", data)


def load_cuts() -> Dict[str, Cut]:
    return _load_items("cuts", Cut)


def delete_cut(cut_id: str):
    _delete_item("cuts", cut_id)


# --- Work ---
def save_work(work: Work):
    data = work.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("works", data)


def load_works() -> Dict[str, Work]:
    return _load_items("works", Work)


def delete_work(work_id: str):
    _delete_item("works", work_id)


# --- Character ---
def save_character(character: Character):
    data = character.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("characters", data)


def load_characters() -> Dict[str, Character]:
    return _load_items("characters", Character)


def delete_character(character_id: str):
    _delete_item("characters", character_id)


# --- Actor ---
def save_actor(actor: Actor):
    data = actor.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("actors", data)


def load_actors() -> Dict[str, Actor]:
    return _load_items("actors", Actor)


def delete_actor(actor_id: str):
    _delete_item("actors", actor_id)


# --- Scene ---
def save_scene(scene: Scene):
    data = scene.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    data["adetailer_enabled"] = 1 if data.get("adetailer_enabled") else 0
    data["adetailer_models"] = list_to_json_str(data.get("adetailer_models", []))
    data["role_assignments"] = dataclass_list_to_json_str(
        data.get("role_assignments", [])
    )
    data["state_categories"] = list_to_json_str(data.get("state_categories", []))
    data["additional_prompt_ids"] = list_to_json_str(
        data.get("additional_prompt_ids", [])
    )
    data["composition_ids"] = list_to_json_str(data.get("composition_ids", []))
    data["sd_param_ids"] = list_to_json_str(data.get("sd_param_ids", []))
    _save_item("scenes", data)


def load_scenes() -> Dict[str, Scene]:
    return _load_items("scenes", Scene)


def delete_scene(scene_id: str):
    _delete_item("scenes", scene_id)


def save_additional_prompt(ap: AdditionalPrompt):
    data = ap.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("additional_prompts", data)


def load_additional_prompts() -> Dict[str, AdditionalPrompt]:
    return _load_items("additional_prompts", AdditionalPrompt)


def delete_additional_prompt(ap_id: str):
    _delete_item("additional_prompts", ap_id)


# --- Simple Parts (Costume, Pose, Expression, Background, Lighting, Composition, Style) ---
def save_costume(costume: Costume):
    data = costume.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    data["color_palette"] = dataclass_list_to_json_str(data.get("color_palette", []))
    data["state_ids"] = list_to_json_str(data.get("state_ids", []))
    _save_item("costumes", data)


def load_costumes() -> Dict[str, Costume]:
    return _load_items("costumes", Costume)


def delete_costume(costume_id: str):
    _delete_item("costumes", costume_id)


def save_state(state: State):
    data = state.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("states", data)


def load_states() -> Dict[str, State]:
    return _load_items("states", State)


def delete_state(state_id: str):
    _delete_item("states", state_id)


def save_pose(pose: Pose):
    data = pose.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("poses", data)


def load_poses() -> Dict[str, Pose]:
    return _load_items("poses", Pose)


def delete_pose(pose_id: str):
    _delete_item("poses", pose_id)


def save_expression(expression: Expression):
    data = expression.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("expressions", data)


def load_expressions() -> Dict[str, Expression]:
    return _load_items("expressions", Expression)


def delete_expression(expression_id: str):
    _delete_item("expressions", expression_id)


def save_background(background: Background):
    data = background.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("backgrounds", data)


def load_backgrounds() -> Dict[str, Background]:
    return _load_items("backgrounds", Background)


def delete_background(background_id: str):
    _delete_item("backgrounds", background_id)


def save_lighting(lighting: Lighting):
    data = lighting.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("lighting", data)


def load_lighting() -> Dict[str, Lighting]:
    return _load_items("lighting", Lighting)


def delete_lighting(lighting_id: str):
    _delete_item("lighting", lighting_id)


def save_composition(composition: Composition):
    data = composition.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("compositions", data)


def load_compositions() -> Dict[str, Composition]:
    return _load_items("compositions", Composition)


def delete_composition(composition_id: str):
    _delete_item("compositions", composition_id)


def save_style(style: Style):
    data = style.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("styles", data)


def load_styles() -> Dict[str, Style]:
    return _load_items("styles", Style)


def delete_style(style_id: str):
    _delete_item("styles", style_id)


# --- SD Params ---
def save_sd_param(param: StableDiffusionParams):
    """StableDiffusionParams プリセットを保存します。"""
    data = param.__dict__.copy()
    conn = get_connection()
    cursor = conn.cursor()
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT OR REPLACE INTO sd_params ({columns}) VALUES ({placeholders})"
    try:
        cursor.execute(sql, list(data.values()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving SD param item to sd_params: {e}")
        conn.rollback()
    finally:
        conn.close()


def load_sd_params() -> Dict[str, StableDiffusionParams]:
    """StableDiffusionParams プリセットをすべてロードします。"""
    return _load_items("sd_params", StableDiffusionParams)


def delete_sd_param(param_id: str):
    """StableDiffusionParams プリセットを削除します。"""
    _delete_item("sd_params", param_id)


# --- State Category ---
def save_state_category(category: StateCategory):
    data = category.__dict__.copy()
    _save_item("state_categories", data)


def load_state_categories() -> Dict[str, StateCategory]:
    return _load_items("state_categories", StateCategory)


def delete_state_category(category_id: str):
    _delete_item("state_categories", category_id)


# --- Sequence ---
def save_sequence(sequence: Sequence):
    data = sequence.__dict__.copy()
    data["scene_entries"] = dataclass_list_to_json_str(data.get("scene_entries", []))
    _save_item("sequences", data)


def load_sequences() -> Dict[str, Sequence]:
    return _load_items("sequences", Sequence)


def delete_sequence(sequence_id: str):
    _delete_item("sequences", sequence_id)


# --- Batch Queue ---
def save_queue_item(queue_item: QueueItem):
    data = queue_item.__dict__.copy()
    data["actor_assignments"] = dict_to_json_str(data.get("actor_assignments", {}))
    data["appearance_overrides"] = dict_to_json_str(
        data.get("appearance_overrides", {})
    )
    data["item_order"] = data.pop("order", 0)  # カラム名に合わせる
    _save_item("batch_queue", data)


def load_batch_queue() -> List[QueueItem]:
    """キューアイテムを order 順にソートしてリストでロードします。"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    items: List[QueueItem] = []
    try:
        cursor.execute("SELECT * FROM batch_queue ORDER BY item_order ASC")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print("テーブル 'batch_queue' が見つかりません。空のリストを返します。")
        rows = []
    finally:
        conn.close()

    class_fields = {f.name for f in QueueItem.__dataclass_fields__.values()}

    for row in rows:
        row_dict_raw = dict(row)
        item_id = row_dict_raw.get("id")
        if not item_id:
            continue

        row_dict = {
            k: v
            for k, v in row_dict_raw.items()
            if k in class_fields or k == "item_order"
        }

        if "actor_assignments" in row_dict and isinstance(
            row_dict["actor_assignments"], str
        ):
            row_dict["actor_assignments"] = json_str_to_dict(
                row_dict["actor_assignments"]
            )
        else:
            row_dict["actor_assignments"] = {}

        if "appearance_overrides" in row_dict and isinstance(
            row_dict["appearance_overrides"], str
        ):
            row_dict["appearance_overrides"] = json_str_to_dict(
                row_dict["appearance_overrides"]
            )
        else:
            row_dict["appearance_overrides"] = {}

        row_dict["order"] = row_dict.pop("item_order", 0)  # カラム名をモデルの属性名に

        try:
            valid_args = {k: v for k, v in row_dict.items() if k in class_fields}
            items.append(QueueItem(**valid_args))
        except Exception as e:
            print(
                f"Error creating instance of QueueItem for id '{item_id}'. Data: {row_dict}. Error: {e}"
            )
            import traceback

            traceback.print_exc()

    return items


def delete_queue_item(queue_item_id: str):
    _delete_item("batch_queue", queue_item_id)


def clear_batch_queue():
    """バッチキューテーブルを空にします。"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM batch_queue")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error clearing batch_queue: {e}")
        conn.rollback()
    finally:
        conn.close()
