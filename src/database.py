# src/database.py
import sqlite3
import json
import os
from typing import Dict, List, Type, TypeVar, Any

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
    # dict_to_json_str, json_str_to_dict, # 未使用なのでコメントアウト
    dataclass_list_to_json_str,
    json_str_to_dataclass_list,
)
from .data.mocks import initialMockDatabase

# Define path relative to this file
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "..", "data", "prompt_data.db")

T = TypeVar("T")  # Generic type variable for dataclasses

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    """データベース接続を取得します。"""
    return sqlite3.connect(DB_PATH)


def initialize_db():
    """データベースファイルとテーブルを作成し、初期データを挿入します。"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # --- 1. すべてのテーブルを CREATE TABLE IF NOT EXISTS で先に作成 ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id TEXT PRIMARY KEY, title_jp TEXT, title_en TEXT,
                tags TEXT, sns_tags TEXT
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, work_id TEXT, tags TEXT,
                personal_color TEXT, underwear_color TEXT
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt TEXT, negative_prompt TEXT,
                character_id TEXT,
                base_costume_id TEXT, base_pose_id TEXT, base_expression_id TEXT
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cuts (
                id TEXT PRIMARY KEY, name TEXT,
                prompt_template TEXT, negative_template TEXT,
                roles TEXT
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                background_id TEXT, lighting_id TEXT, composition_id TEXT,
                cut_id TEXT, -- ★ cuts を cut_id に変更
                role_directions TEXT,
                reference_image_path TEXT, image_mode TEXT
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS directions (
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
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                    prompt TEXT, negative_prompt TEXT
                    {extra_columns}
                )""")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sd_params (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                steps INTEGER, sampler_name TEXT, cfg_scale REAL,
                seed INTEGER, width INTEGER, height INTEGER,
                denoising_strength REAL
            )""")

        # --- 2. カラム修正 (ALTER TABLE) を実行 ---
        # Character テーブルのカラム追加
        cursor.execute("PRAGMA table_info(characters)")
        columns = {col[1] for col in cursor.fetchall()}
        if "personal_color" not in columns:
            cursor.execute("ALTER TABLE characters ADD COLUMN personal_color TEXT")
        if "underwear_color" not in columns:
            cursor.execute("ALTER TABLE characters ADD COLUMN underwear_color TEXT")

        # Costume テーブルのカラム修正
        cursor.execute("PRAGMA table_info(costumes)")
        columns = {col[1] for col in cursor.fetchall()}
        if "color_placeholders" in columns and "color_palette" not in columns:
            print(
                "INFO: Found legacy 'color_placeholders' column. Adding 'color_palette' column."
            )
            cursor.execute("ALTER TABLE costumes ADD COLUMN color_palette TEXT")
        elif "color_palette" not in columns:
            cursor.execute("ALTER TABLE costumes ADD COLUMN color_palette TEXT")

        # actors テーブルに character_id カラムを追加
        cursor.execute("PRAGMA table_info(actors)")
        columns = {col[1] for col in cursor.fetchall()}
        if "character_id" not in columns:
            print("[INFO] Adding missing 'character_id' column to 'actors' table.")
            cursor.execute("ALTER TABLE actors ADD COLUMN character_id TEXT")

        # scenes テーブルの移行 (cuts カラム削除 -> cut_id カラム追加)
        cursor.execute("PRAGMA table_info(scenes)")
        scene_columns = {col[1] for col in cursor.fetchall()}
        if "prompt_template" in scene_columns or "cuts" in scene_columns:
            print("[INFO] Found old columns in 'scenes' table. Attempting migration...")
            # ALTER TABLE DROP COLUMN は SQLite 3.35.0 以降なので使わない
            # テーブルを作り直すのが安全
            try:
                # 1. 既存テーブルをリネーム
                cursor.execute("ALTER TABLE scenes RENAME TO scenes_old")
                print("[INFO] Renamed 'scenes' to 'scenes_old'.")
                # 2. 新しいスキーマでテーブル再作成
                cursor.execute("""
                    CREATE TABLE scenes (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                        background_id TEXT, lighting_id TEXT, composition_id TEXT,
                        cut_id TEXT,
                        role_directions TEXT,
                        reference_image_path TEXT, image_mode TEXT
                    )""")
                print("[INFO] Created new 'scenes' table with updated schema.")
                # 3. データ移行は行わない (旧データは破棄)
                #    必要なら SELECT して INSERT する処理をここに追加
                # cursor.execute("DROP TABLE scenes_old") # 旧テーブル削除
            except sqlite3.OperationalError as e:
                print(
                    f"[WARN] Could not migrate 'scenes' table schema automatically: {e}"
                )
                # 既に新しいスキーマの場合など
                if "cut_id" not in scene_columns:
                    # ここで cut_id を追加する方が安全かも
                    try:
                        cursor.execute("ALTER TABLE scenes ADD COLUMN cut_id TEXT")
                    except sqlite3.OperationalError:
                        pass  # カラムが既に存在するなど

        elif "cut_id" not in scene_columns:  # 新規作成でもカラムがない場合
            print("[INFO] Adding 'cut_id' column to 'scenes' table.")
            cursor.execute("ALTER TABLE scenes ADD COLUMN cut_id TEXT")

        # 古い sd_params テーブルからデータを移行 (簡易的)
        try:
            cursor.execute("PRAGMA table_info(sd_params)")
            new_columns = {col[1] for col in cursor.fetchall()}

            old_table_exists = False
            if "key" in new_columns:  # まだ古いテーブルレイアウトの場合
                print("[INFO] Found old 'sd_params' table (key-value). Migrating...")
                try:
                    cursor.execute("ALTER TABLE sd_params RENAME TO sd_params_old")
                    print("[INFO] Renamed 'sd_params' to 'sd_params_old'.")
                    old_table_exists = True
                except sqlite3.OperationalError as e:
                    print(
                        f"[WARN] Could not rename old sd_params table (might already exist): {e}"
                    )
                    if "already exists" in str(e):
                        cursor.execute("DROP TABLE sd_params")
                        print("[INFO] Dropped problematic old 'sd_params' table.")

                cursor.execute("""
                    CREATE TABLE sd_params (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL,
                        steps INTEGER, sampler_name TEXT, cfg_scale REAL,
                        seed INTEGER, width INTEGER, height INTEGER,
                        denoising_strength REAL
                    )""")

            cursor.execute("SELECT COUNT(*) FROM sd_params")
            new_count = cursor.fetchone()[0]

            if old_table_exists and new_count == 0:
                print("[INFO] Migrating data from 'sd_params_old'...")
                params_dict = {}
                try:
                    cursor.execute("SELECT key, value FROM sd_params_old")
                    rows = cursor.fetchall()
                    params_dict = {key: value for key, value in rows}

                    default_preset = StableDiffusionParams(
                        id="sdp_default_migrated",
                        name="Migrated Default",
                        steps=int(params_dict.get("steps", 20)),
                        sampler_name=params_dict.get("sampler_name", "Euler a"),
                        cfg_scale=float(params_dict.get("cfg_scale", 7.0)),
                        seed=int(params_dict.get("seed", -1)),
                        width=int(params_dict.get("width", 512)),
                        height=int(params_dict.get("height", 512)),
                        denoising_strength=float(
                            params_dict.get("denoising_strength", 0.6)
                        ),
                    )
                    cursor.execute(
                        """INSERT INTO sd_params (id, name, steps, sampler_name, cfg_scale, seed, width, height, denoising_strength)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            default_preset.id,
                            default_preset.name,
                            default_preset.steps,
                            default_preset.sampler_name,
                            default_preset.cfg_scale,
                            default_preset.seed,
                            default_preset.width,
                            default_preset.height,
                            default_preset.denoising_strength,
                        ),
                    )
                    print("[INFO] Migration successful.")
                    # cursor.execute("DROP TABLE sd_params_old")
                except Exception as e:
                    print(
                        f"[ERROR] Failed to migrate sd_params data: {e}. Skipping migration."
                    )

        except sqlite3.Error as e:
            print(f"[WARN] Error during sd_params table migration check: {e}")

        # --- 初期データの挿入 ---
        cursor.execute("SELECT COUNT(*) FROM cuts")
        cut_count = cursor.fetchone()[0]
        if cut_count == 0:
            print("データベースが空のようです。初期データを挿入します...")
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
            print("初期データの挿入が完了しました。")
        else:
            print(
                "データベースには既にデータが存在するため、初期データの挿入はスキップされました。"
            )

        conn.commit()
    except sqlite3.Error as e:
        print(f"データベース初期化中にエラーが発生しました: {e}")
        conn.rollback()
    finally:
        conn.close()
    print(
        f"データベースが初期化されました（または既存データを確認しました）: {DB_PATH}"
    )


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
    """汎用: 指定された型の全アイテムをロードします。"""
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

    for row in rows:
        row_dict = dict(row)
        item_id = row_dict.get("id")
        if not item_id:
            continue

        # --- JSON 文字列 -> リスト 変換処理 ---
        if "tags" in row_dict and isinstance(row_dict["tags"], str):
            try:
                row_dict["tags"] = json.loads(row_dict["tags"])
            except json.JSONDecodeError:
                row_dict["tags"] = []

        # ★ Scene: role_directions の処理のみ
        if class_type == Scene:
            row_dict["role_directions"] = json_str_to_list(
                row_dict.get("role_directions"), RoleDirection
            )
            # cut_id は TEXT なので変換不要
            # 古い属性の削除
            row_dict.pop("prompt_template", None)
            row_dict.pop("negative_template", None)
            row_dict.pop("roles", None)
            row_dict.pop("cuts", None)  # 古い cuts カラムも削除

        # ★ Cut: roles の処理
        if class_type == Cut:
            row_dict["roles"] = json_str_to_list(row_dict.get("roles"), SceneRole)

        # ★ Costume: color_palette の処理
        if class_type == Costume:
            color_palette_json = row_dict.get("color_palette") or row_dict.get(
                "color_placeholders"
            )
            palette_list = json_str_to_dataclass_list(
                color_palette_json, ColorPaletteItem
            )
            row_dict["color_palette"] = palette_list if palette_list else []
            row_dict.pop("color_placeholders", None)

        # ★ Actor: 古い属性の削除
        if class_type == Actor:
            row_dict.pop("work_title", None)
            row_dict.pop("character_name", None)

        try:
            items[item_id] = class_type(**row_dict)
        except Exception as e:
            print(
                f"Error creating instance of {class_type.__name__} for id '{item_id}'. Row data: {row_dict}. Error: {e}"
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


# --- Cut 用関数 (変更なし) ---
def save_cut(cut: Cut):
    data = cut.__dict__.copy()
    data["roles"] = list_to_json_str(data.get("roles", []))
    _save_item("cuts", data)


def load_cuts() -> Dict[str, Cut]:
    return _load_items("cuts", Cut)


def delete_cut(cut_id: str):
    _delete_item("cuts", cut_id)


# --- Work 用関数 (変更なし) ---
def save_work(work: Work):
    data = work.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("works", data)


def load_works() -> Dict[str, Work]:
    return _load_items("works", Work)


def delete_work(work_id: str):
    _delete_item("works", work_id)


# --- Character 用関数 (変更なし) ---
def save_character(character: Character):
    data = character.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("characters", data)


def load_characters() -> Dict[str, Character]:
    return _load_items("characters", Character)


def delete_character(character_id: str):
    _delete_item("characters", character_id)


# --- Actor 用関数 (変更なし) ---
def save_actor(actor: Actor):
    data = actor.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("actors", data)


def load_actors() -> Dict[str, Actor]:
    return _load_items("actors", Actor)


def delete_actor(actor_id: str):
    _delete_item("actors", actor_id)


# --- Scene 用関数 (修正済み) ---
def save_scene(scene: Scene):
    data = scene.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    data["cut_id"] = data.get("cut_id")  # get で存在確認
    data["role_directions"] = list_to_json_str(data.get("role_directions", []))
    # 不要な属性を削除
    data.pop("cuts", None)
    data.pop("prompt_template", None)
    data.pop("negative_template", None)
    data.pop("roles", None)
    _save_item("scenes", data)


def load_scenes() -> Dict[str, Scene]:
    return _load_items("scenes", Scene)


def delete_scene(scene_id: str):
    _delete_item("scenes", scene_id)


# --- Direction 用関数 (変更なし) ---
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


# --- Pose (変更なし) ---
def save_pose(pose: Pose):
    data = pose.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("poses", data)


def load_poses() -> Dict[str, Pose]:
    return _load_items("poses", Pose)


def delete_pose(pose_id: str):
    _delete_item("poses", pose_id)


# --- Expression (変更なし) ---
def save_expression(expression: Expression):
    data = expression.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("expressions", data)


def load_expressions() -> Dict[str, Expression]:
    return _load_items("expressions", Expression)


def delete_expression(expression_id: str):
    _delete_item("expressions", expression_id)


# --- Background (変更なし) ---
def save_background(background: Background):
    data = background.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("backgrounds", data)


def load_backgrounds() -> Dict[str, Background]:
    return _load_items("backgrounds", Background)


def delete_background(background_id: str):
    _delete_item("backgrounds", background_id)


# --- Lighting (変更なし) ---
def save_lighting(lighting: Lighting):
    data = lighting.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("lighting", data)


def load_lighting() -> Dict[str, Lighting]:
    return _load_items("lighting", Lighting)


def delete_lighting(lighting_id: str):
    _delete_item("lighting", lighting_id)


# --- Composition (変更なし) ---
def save_composition(composition: Composition):
    data = composition.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("compositions", data)


def load_compositions() -> Dict[str, Composition]:
    return _load_items("compositions", Composition)


def delete_composition(composition_id: str):
    _delete_item("compositions", composition_id)


# --- Style (変更なし) ---
def save_style(style: Style):
    data = style.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("styles", data)


def load_styles() -> Dict[str, Style]:
    return _load_items("styles", Style)


def delete_style(style_id: str):
    _delete_item("styles", style_id)


# --- SD Params Save/Load/Delete (修正済み) ---
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
