# src/database.py
import sqlite3
import json
import os
from typing import Dict, List, Type, TypeVar, Any

# ★ 修正: FullDatabase は import しない, Helper関数を import
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
    SceneRole,
    RoleDirection,
    ColorPaletteItem,
    CharacterColorRef,
)
from .utils.json_helpers import (
    list_to_json_str,
    json_str_to_list,
    dict_to_json_str,
    json_str_to_dict,
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
        # カラムが存在しない場合のみ追加 (より安全な方法)
        cursor.execute("PRAGMA table_info(characters)")
        columns = [col[1] for col in cursor.fetchall()]
        if "personal_color" not in columns:
            cursor.execute("ALTER TABLE characters ADD COLUMN personal_color TEXT")
        if "underwear_color" not in columns:
            cursor.execute("ALTER TABLE characters ADD COLUMN underwear_color TEXT")
        # --- ★ Costume テーブル修正 ---
        # カラムが存在しない場合のみ追加
        cursor.execute("PRAGMA table_info(costumes)")
        columns = [col[1] for col in cursor.fetchall()]
        if "color_placeholders" in columns:
            # 古いカラム名をリネーム (SQLiteの制限により複雑になるため、ここでは削除して再作成を推奨)
            # または、データを保持したい場合は手動での移行が必要
            print(
                "INFO: Renaming 'color_placeholders' column to 'color_palette' in 'costumes' table is recommended."
            )
            # 簡単な移行 (カラム追加 -> データコピー -> 古いカラム削除)
            if "color_palette" not in columns:
                cursor.execute("ALTER TABLE costumes ADD COLUMN color_palette TEXT")
                # ここで古いデータを新しい形式に変換してコピーするロジックが必要
                # cursor.execute("UPDATE costumes SET color_palette = ... WHERE color_placeholders IS NOT NULL")
                # cursor.execute("ALTER TABLE costumes DROP COLUMN color_placeholders") # SQLiteはDROP COLUMNをサポートしない場合が多い
        elif "color_palette" not in columns:
            cursor.execute(
                "ALTER TABLE costumes ADD COLUMN color_palette TEXT"
            )  # 新しいカラム名で追加
        # --- ★ Work テーブル作成 ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id TEXT PRIMARY KEY, title_jp TEXT, title_en TEXT,
                tags TEXT, sns_tags TEXT
            )""")
        # --- ★ Character テーブル作成 ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, work_id TEXT, tags TEXT
            )""")
        # --- ★ Actor テーブル修正 ---
        # cursor.execute(
        #    """ DROP TABLE IF EXISTS actors """
        # )  # 古い構造を削除（開発中のみ）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt TEXT, negative_prompt TEXT,
                character_id TEXT, -- 変更
                base_costume_id TEXT, base_pose_id TEXT, base_expression_id TEXT
                -- work_title, character_name 削除
            )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                prompt_template TEXT, negative_template TEXT,
                background_id TEXT, lighting_id TEXT, composition_id TEXT,
                roles TEXT, role_directions TEXT,
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
        ]
        for table_name in simple_parts_tables:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                    prompt TEXT, negative_prompt TEXT
                )""")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sd_params ( key TEXT PRIMARY KEY, value TEXT )""")

        # --- 初期データの挿入 ---
        cursor.execute("SELECT COUNT(*) FROM works")  # Work テーブルで確認
        scene_count = cursor.fetchone()[0]

        if scene_count == 0:
            print("データベースが空のようです。初期データを挿入します...")
            for work in initialMockDatabase.works.values():
                save_work(work)
            for character in initialMockDatabase.characters.values():
                save_character(character)
            for actor in initialMockDatabase.actors.values():
                save_actor(actor)
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
            save_sd_params(initialMockDatabase.sdParams)
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
        conn.rollback()  # エラー時はロールバック
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

        # --- ★ JSON 文字列 -> リスト 変換処理 ---
        # tags フィールドを持つすべてのクラスで共通処理
        if "tags" in row_dict and isinstance(row_dict["tags"], str):
            try:
                row_dict["tags"] = json.loads(row_dict["tags"])
            except json.JSONDecodeError:
                row_dict["tags"] = []

        # Scene 固有の処理
        if class_type == Scene:
            # json_str_to_list ヘルパーを使う
            row_dict["roles"] = json_str_to_list(row_dict.get("roles"), SceneRole)
            row_dict["role_directions"] = json_str_to_list(
                row_dict.get("role_directions"), RoleDirection
            )

        color_palette_json = row_dict.get("color_palette") or row_dict.get(
            "color_placeholders"
        )
        if class_type == Costume and color_palette_json:
            # ★ データクラスリスト用ヘルパーを使用
            row_dict["color_palette"] = json_str_to_dataclass_list(
                color_palette_json, ColorPaletteItem
            )
            # 古いカラムが存在すれば削除
            if "color_placeholders" in row_dict:
                del row_dict["color_placeholders"]
        elif class_type == Costume and "color_palette" not in row_dict:
            row_dict["color_palette"] = []  # カラム自体がない場合も空リストで初期化

        try:
            # --- ★ CharacterColorRef の Enum 変換 ---
            # Costume.color_palette 内の color_ref が文字列で読み込まれるため Enum に変換
            if class_type == Costume and "color_palette" in row_dict:
                for item in row_dict["color_palette"]:
                    if isinstance(item, ColorPaletteItem) and isinstance(
                        item.color_ref, str
                    ):
                        try:
                            item.color_ref = CharacterColorRef(item.color_ref)
                        except ValueError:
                            print(
                                f"Warning: Invalid CharacterColorRef value '{item.color_ref}' found in Costume {item_id}. Setting to default."
                            )
                            item.color_ref = list(CharacterColorRef)[
                                0
                            ]  # デフォルト値 (例: PERSONAL_COLOR)
            items[item_id] = class_type(**row_dict)
        except Exception as e:  # より広範なエラーをキャッチ
            # dataclassのフィールドとDBのカラムが一致しない場合や型変換エラーなど
            print(
                f"Error creating instance of {class_type.__name__} for id '{item_id}'. Row data: {row_dict}. Error: {e}"
            )

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
# (各関数は汎用関数を呼び出すだけ)


# --- ★ Work 用関数 ---
def save_work(work: Work):
    data = work.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("works", data)


def load_works() -> Dict[str, Work]:
    return _load_items("works", Work)


def delete_work(work_id: str):
    # TODO: 関連する Character や Actor の扱いをどうするか？ (今回は単純削除)
    _delete_item("works", work_id)


# --- ★ Character 用関数 ---
def save_character(character: Character):
    data = character.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("characters", data)


def load_characters() -> Dict[str, Character]:
    return _load_items("characters", Character)


def delete_character(character_id: str):
    # TODO: 関連する Actor の扱いをどうするか？ (今回は単純削除)
    _delete_item("characters", character_id)


# --- ★ Actor 用関数 (修正) ---
def save_actor(actor: Actor):
    data = actor.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    # work_title, character_name はもうない
    _save_item("actors", data)


def load_actors() -> Dict[str, Actor]:
    return _load_items("actors", Actor)  # _load_items 側で tags は処理されるはず


def delete_actor(actor_id: str):
    _delete_item("actors", actor_id)


def save_scene(scene: Scene):
    data = scene.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    # ★ models.py のヘルパー関数を使用
    data["roles"] = list_to_json_str(data.get("roles", []))
    data["role_directions"] = list_to_json_str(data.get("role_directions", []))
    _save_item("scenes", data)


def load_scenes() -> Dict[str, Scene]:
    return _load_items("scenes", Scene)


def delete_scene(scene_id: str):
    _delete_item("scenes", scene_id)


def save_direction(direction: Direction):
    data = direction.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("directions", data)


def load_directions() -> Dict[str, Direction]:
    return _load_items("directions", Direction)


def delete_direction(direction_id: str):
    _delete_item("directions", direction_id)


# --- Simple Parts (例: Costume) ---
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


# --- SD Params Save/Load ---
def save_sd_params(params: StableDiffusionParams):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for key, value in params.__dict__.items():
            cursor.execute(
                "INSERT OR REPLACE INTO sd_params (key, value) VALUES (?, ?)",
                (key, str(value)),
            )  # 全て文字列として保存
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving SD params: {e}")
        conn.rollback()
    finally:
        conn.close()


def load_sd_params() -> StableDiffusionParams:
    conn = get_connection()
    cursor = conn.cursor()
    params_dict = {}
    try:
        cursor.execute("SELECT key, value FROM sd_params")
        rows = cursor.fetchall()
        params_dict = {key: value for key, value in rows}
    except sqlite3.OperationalError:
        print("SD Params table not found, using defaults.")
    except sqlite3.Error as e:
        print(f"Error loading SD params: {e}")
    finally:
        conn.close()

    # 文字列から正しい型に変換して dataclass を作成
    try:
        return StableDiffusionParams(
            steps=int(params_dict.get("steps", 20)),
            sampler_name=params_dict.get("sampler_name", "Euler a"),
            cfg_scale=float(params_dict.get("cfg_scale", 7.0)),
            seed=int(params_dict.get("seed", -1)),
            width=int(params_dict.get("width", 512)),
            height=int(params_dict.get("height", 512)),
            denoising_strength=float(params_dict.get("denoising_strength", 0.6)),
        )
    except (ValueError, TypeError) as e:
        print(f"Error converting SD params, using defaults: {e}")
        return StableDiffusionParams()  # エラー時はデフォルト値を返す
