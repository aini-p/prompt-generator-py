# src/database.py
import sqlite3
import json
import os
from typing import Dict, List, Type, TypeVar, Any

# モデルとヘルパー関数をインポート
from .models import (
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
    StableDiffusionParams,
    Cut,
    SceneRole,
    RoleDirection,
    Style,
    ColorPaletteItem,
)
from .utils.json_helpers import (
    list_to_json_str,
    json_str_to_list,
    dataclass_list_to_json_str,
    json_str_to_dataclass_list,
)

# 初期データをインポート
from .data.mocks import initialMockDatabase

# --- 定数定義 ---
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "..", "data", "prompt_data.db")
T = TypeVar("T")  # ジェネリック型

# data ディレクトリ作成
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


# --- データベース接続 ---
def get_connection():
    """データベース接続を取得します。"""
    return sqlite3.connect(DB_PATH)


# --- データベース初期化 ---
def initialize_db():
    """
    データベースファイルとテーブルを (再) 作成し、初期データを挿入します。
    古いスキーマやデータ移行は考慮せず、常に最新のスキーマで作成します。
    """
    # 既存のDBファイルがあれば削除 (常に初期化するため)
    if os.path.exists(DB_PATH):
        print(f"[INFO] Deleting existing database file: {DB_PATH}")
        try:
            os.remove(DB_PATH)
        except OSError as e:
            print(f"[ERROR] Could not delete existing database file: {e}")
            # エラーが発生しても続行を試みる (テーブル作成で失敗する可能性あり)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        print("[INFO] Creating database tables with the latest schema...")
        # --- テーブル作成 (CREATE TABLE IF NOT EXISTS) ---
        cursor.execute("""
            CREATE TABLE works (
                id TEXT PRIMARY KEY, title_jp TEXT, title_en TEXT,
                tags TEXT, sns_tags TEXT
            )""")
        cursor.execute("""
            CREATE TABLE characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, work_id TEXT, tags TEXT,
                personal_color TEXT, underwear_color TEXT
            )""")
        cursor.execute("""
            CREATE TABLE actors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt TEXT, negative_prompt TEXT,
                character_id TEXT,
                base_costume_id TEXT, base_pose_id TEXT, base_expression_id TEXT
            )""")
        cursor.execute("""
            CREATE TABLE cuts (
                id TEXT PRIMARY KEY, name TEXT,
                prompt_template TEXT, negative_template TEXT,
                roles TEXT
            )""")
        cursor.execute("""
            CREATE TABLE scenes (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                background_id TEXT, lighting_id TEXT, composition_id TEXT,
                cut_id TEXT, -- ★ 最新スキーマ
                role_directions TEXT,
                reference_image_path TEXT, image_mode TEXT
            )""")
        cursor.execute("""
            CREATE TABLE directions (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt TEXT, negative_prompt TEXT,
                costume_id TEXT, pose_id TEXT, expression_id TEXT
            )""")

        simple_parts_tables = [
            "costumes",
            "poses",
            "expressions",
            "backgrounds",
            "lighting",
            "compositions",
            "styles",
        ]
        for table_name in simple_parts_tables:
            extra_columns = ", color_palette TEXT" if table_name == "costumes" else ""
            cursor.execute(f"""
                CREATE TABLE {table_name} ( -- IF NOT EXISTS は不要 (DB削除前提のため)
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                    prompt TEXT, negative_prompt TEXT
                    {extra_columns}
                )""")

        cursor.execute("""
            CREATE TABLE sd_params ( -- ★ 最新スキーマ
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                steps INTEGER, sampler_name TEXT, cfg_scale REAL,
                seed INTEGER, width INTEGER, height INTEGER,
                denoising_strength REAL
            )""")

        print("[INFO] Database tables created.")

        # --- 初期データの挿入 ---
        print("[INFO] Inserting initial mock data...")
        for work in initialMockDatabase.works.values():
            save_work(work)
        for character in initialMockDatabase.characters.values():
            save_character(character)
        for actor in initialMockDatabase.actors.values():
            save_actor(actor)
        for cut in initialMockDatabase.cuts.values():
            save_cut(cut)
        for scene in initialMockDatabase.scenes.values():
            save_scene(scene)
        for direction in initialMockDatabase.directions.values():
            save_direction(direction)
        for costume in initialMockDatabase.costumes.values():
            save_costume(costume)
        for pose in initialMockDatabase.poses.values():
            save_pose(pose)
        for expression in initialMockDatabase.expressions.values():
            save_expression(expression)
        for background in initialMockDatabase.backgrounds.values():
            save_background(background)
        for lighting in initialMockDatabase.lighting.values():
            save_lighting(lighting)
        for composition in initialMockDatabase.compositions.values():
            save_composition(composition)
        for style in initialMockDatabase.styles.values():
            save_style(style)
        for param in initialMockDatabase.sdParams.values():
            save_sd_param(param)
        print("[INFO] Initial mock data inserted.")

        conn.commit()
    except sqlite3.Error as e:
        print(f"データベース初期化中にエラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()
    print(f"データベースが初期化されました: {DB_PATH}")


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
    """汎用: 指定された型の全アイテムをロードします。古い属性は無視します。"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    items: Dict[str, T] = {}
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print(f"テーブル '{table_name}' が見つかりません。空の辞書を返します。")
        rows = []
    finally:
        conn.close()

    # dataclass のフィールド名を取得
    class_fields = {f.name for f in class_type.__dataclass_fields__.values()}

    for row in rows:
        row_dict_raw = dict(row)
        item_id = row_dict_raw.get("id")
        if not item_id:
            continue

        # dataclass に存在するフィールドのみを抽出
        row_dict = {k: v for k, v in row_dict_raw.items() if k in class_fields}

        # --- JSON 文字列 -> リスト 変換処理 ---
        if "tags" in row_dict and isinstance(row_dict["tags"], str):
            try:
                row_dict["tags"] = json.loads(row_dict["tags"])
            except json.JSONDecodeError:
                row_dict["tags"] = []

        if class_type == Scene and "role_directions" in row_dict:
            row_dict["role_directions"] = json_str_to_list(
                row_dict.get("role_directions"), RoleDirection
            )

        if class_type == Cut and "roles" in row_dict:
            row_dict["roles"] = json_str_to_list(row_dict.get("roles"), SceneRole)

        if class_type == Costume and "color_palette" in row_dict:
            palette_list = json_str_to_dataclass_list(
                row_dict.get("color_palette"), ColorPaletteItem
            )
            row_dict["color_palette"] = palette_list if palette_list else []

        try:
            # dataclass に存在するフィールドのみでインスタンス化
            items[item_id] = class_type(**row_dict)
        except Exception as e:
            print(
                f"Error creating instance of {class_type.__name__} for id '{item_id}'. Filtered data: {row_dict}. Error: {e}"
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
# (各関数は汎用関数を呼び出すだけ、または型固有の処理を行う)


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
    data["cut_id"] = data.get("cut_id")  # Optional[str]
    data["role_directions"] = list_to_json_str(data.get("role_directions", []))
    # 古い属性は dataclass にないので pop 不要
    _save_item("scenes", data)


def load_scenes() -> Dict[str, Scene]:
    return _load_items("scenes", Scene)


def delete_scene(scene_id: str):
    _delete_item("scenes", scene_id)


# --- Direction ---
def save_direction(direction: Direction):
    data = direction.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("directions", data)


def load_directions() -> Dict[str, Direction]:
    return _load_items("directions", Direction)


def delete_direction(direction_id: str):
    _delete_item("directions", direction_id)


# --- Simple Parts (Costume, Pose, Expression, Background, Lighting, Composition, Style) ---
def save_costume(costume: Costume):
    data = costume.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    data["color_palette"] = dataclass_list_to_json_str(data.get("color_palette", []))
    _save_item("costumes", data)


def load_costumes() -> Dict[str, Costume]:
    return _load_items("costumes", Costume)


def delete_costume(costume_id: str):
    _delete_item("costumes", costume_id)


# --- Pose ---
def save_pose(pose: Pose):
    data = pose.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("poses", data)


def load_poses() -> Dict[str, Pose]:
    return _load_items("poses", Pose)


def delete_pose(pose_id: str):
    _delete_item("poses", pose_id)


# --- Expression ---
def save_expression(expression: Expression):
    data = expression.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("expressions", data)


def load_expressions() -> Dict[str, Expression]:
    return _load_items("expressions", Expression)


def delete_expression(expression_id: str):
    _delete_item("expressions", expression_id)


# --- Background ---
def save_background(background: Background):
    data = background.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("backgrounds", data)


def load_backgrounds() -> Dict[str, Background]:
    return _load_items("backgrounds", Background)


def delete_background(background_id: str):
    _delete_item("backgrounds", background_id)


# --- Lighting ---
def save_lighting(lighting: Lighting):
    data = lighting.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("lighting", data)


def load_lighting() -> Dict[str, Lighting]:
    return _load_items("lighting", Lighting)


def delete_lighting(lighting_id: str):
    _delete_item("lighting", lighting_id)


# --- Composition ---
def save_composition(composition: Composition):
    data = composition.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("compositions", data)


def load_compositions() -> Dict[str, Composition]:
    return _load_items("compositions", Composition)


def delete_composition(composition_id: str):
    _delete_item("compositions", composition_id)


# --- Style ---
def save_style(style: Style):
    data = style.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("styles", data)


def load_styles() -> Dict[str, Style]:
    return _load_items("styles", Style)


def delete_style(style_id: str):
    _delete_item("styles", style_id)


# --- SD Params Save/Load/Delete (リファクタリング済み) ---
def save_sd_param(param: StableDiffusionParams):
    """StableDiffusionParams プリセットを保存します。"""
    data = param.__dict__.copy()
    # _save_item は使わず直接 SQL を実行 (型が混在するため)
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
    # _load_items を使用 (型変換は dataclass が行う)
    return _load_items("sd_params", StableDiffusionParams)


def delete_sd_param(param_id: str):
    """StableDiffusionParams プリセットを削除します。"""
    _delete_item("sd_params", param_id)
