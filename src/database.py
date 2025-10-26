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
    Sequence,
    SequenceSceneEntry,
    QueueItem,
)
from .utils.json_helpers import (
    list_to_json_str,
    json_str_to_list,
    dataclass_list_to_json_str,
    json_str_to_dataclass_list,
    dict_to_json_str,
    json_str_to_dict,
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


# --- ▼▼▼ データベース初期化 を修正 ▼▼▼ ---
def initialize_db():
    """
    データベースファイルが存在しない場合は作成し、必要なテーブルが存在しない場合は作成します。
    テーブルが新規に作成された場合のみ、初期データを挿入します。
    """
    # ▼▼▼ ファイル削除処理を削除 ▼▼▼
    # if os.path.exists(DB_PATH):
    #     print(f"[INFO] Deleting existing database file: {DB_PATH}")
    #     try:
    #         os.remove(DB_PATH)
    #     except OSError as e:
    #         print(f"[ERROR] Could not delete existing database file: {e}")
    # ▲▲▲ 削除ここまで ▲▲▲

    conn = get_connection()
    cursor = conn.cursor()
    db_existed = os.path.exists(DB_PATH)  # 接続前に存在したか確認 (厳密ではないが目安)
    tables_created_count = 0  # 新規作成されたテーブル数をカウント

    try:
        print("[INFO] Ensuring database tables exist...")
        # --- テーブル作成 (CREATE TABLE IF NOT EXISTS に変更) ---
        # ▼▼▼ IF NOT EXISTS を追加 ▼▼▼
        created = (
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id TEXT PRIMARY KEY, title_jp TEXT, title_en TEXT,
                tags TEXT, sns_tags TEXT
            )""").rowcount
            > 0
        )  # executeはCursorを返すのでrowcountなどで実行結果を確認する（ただしCREATE TABLEでは意味がない場合が多い）
        # テーブル存在確認のより確実な方法
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='works'"
        )
        works_table_existed = cursor.fetchone() is not None

        created = (
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, work_id TEXT, tags TEXT,
                personal_color TEXT, underwear_color TEXT
            )""").rowcount
            > 0
        )
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='characters'"
        )
        characters_table_existed = cursor.fetchone() is not None

        # ... (他のテーブルも同様に IF NOT EXISTS を追加) ...
        cursor.execute("""CREATE TABLE IF NOT EXISTS actors (...)""")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='actors'"
        )
        actors_table_existed = cursor.fetchone() is not None

        cursor.execute("""CREATE TABLE IF NOT EXISTS cuts (...)""")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cuts'"
        )
        cuts_table_existed = cursor.fetchone() is not None

        cursor.execute("""CREATE TABLE IF NOT EXISTS scenes (...)""")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scenes'"
        )
        scenes_table_existed = cursor.fetchone() is not None

        cursor.execute("""CREATE TABLE IF NOT EXISTS directions (...)""")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='directions'"
        )
        directions_table_existed = cursor.fetchone() is not None

        simple_parts_tables = [
            "costumes",
            "poses",
            "expressions",
            "backgrounds",
            "lighting",
            "compositions",
            "styles",
        ]
        simple_parts_tables_existed = {}
        for table_name in simple_parts_tables:
            extra_columns = ", color_palette TEXT" if table_name == "costumes" else ""
            created = (
                cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
                    prompt TEXT, negative_prompt TEXT {extra_columns}
                )""").rowcount
                > 0
            )
            cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            )
            simple_parts_tables_existed[table_name] = cursor.fetchone() is not None

        created = (
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sd_params (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                steps INTEGER, sampler_name TEXT, cfg_scale REAL,
                seed INTEGER, width INTEGER, height INTEGER,
                denoising_strength REAL
            )""").rowcount
            > 0
        )
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sd_params'"
        )
        sd_params_table_existed = cursor.fetchone() is not None

        created = (
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sequences (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, scene_entries TEXT
            )""").rowcount
            > 0
        )
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sequences'"
        )
        sequences_table_existed = cursor.fetchone() is not None

        created = (
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_queue (
                id TEXT PRIMARY KEY, sequence_id TEXT NOT NULL,
                actor_assignments TEXT, item_order INTEGER
            )""").rowcount
            > 0
        )
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='batch_queue'"
        )
        batch_queue_table_existed = cursor.fetchone() is not None

        # --- テーブルが存在しなかった（=新規作成された）場合のみ初期データを挿入 ---
        # (より単純化：どれか一つでもテーブルが存在しなかったら初期データを入れる、
        #  または、特定のテーブル（例：works）が存在しなかったら初期データを入れる)
        # ここでは works テーブルが存在しなかった場合を基準とする
        if not works_table_existed:
            print(
                "[INFO] Initializing database with mock data as 'works' table was missing..."
            )
            # --- 初期データの挿入 ---
            print("[INFO] Inserting initial mock data...")
            try:
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
                # Sequence や Queue の初期データは mocks.py にないので省略
                print("[INFO] Initial mock data inserted.")
            except Exception as insert_e:
                print(f"[ERROR] Failed to insert initial data: {insert_e}")
                conn.rollback()  # データ挿入に失敗したらロールバック
                raise  # エラーを再送出して初期化失敗を知らせる
        else:
            print(
                "[INFO] Database tables already exist. Skipping initial data insertion."
            )

        conn.commit()
    except sqlite3.Error as e:
        print(f"データベース初期化中にエラーが発生しました: {e}")
        conn.rollback()  # スキーマ作成中のエラーでもロールバック
    finally:
        conn.close()
    print(f"データベースの準備が完了しました: {DB_PATH}")


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
        if class_type == Sequence and "scene_entries" in row_dict:
            row_dict["scene_entries"] = json_str_to_list(
                row_dict.get("scene_entries"), SequenceSceneEntry
            )
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


# --- ▼▼▼ Sequence 用関数 ▼▼▼ ---
def save_sequence(sequence: Sequence):
    data = sequence.__dict__.copy()
    # scene_entries リストをJSON文字列に変換
    data["scene_entries"] = dataclass_list_to_json_str(data.get("scene_entries", []))
    _save_item("sequences", data)


def load_sequences() -> Dict[str, Sequence]:
    return _load_items("sequences", Sequence)


def delete_sequence(sequence_id: str):
    _delete_item("sequences", sequence_id)


# --- ▼▼▼ Batch Queue 用関数 ▼▼▼ ---
def save_queue_item(queue_item: QueueItem):
    data = queue_item.__dict__.copy()
    # actor_assignments 辞書をJSON文字列に変換
    data["actor_assignments"] = dict_to_json_str(data.get("actor_assignments", {}))
    # 'order' を 'item_order' カラム名にマッピング (モデルとDBカラム名が違う場合)
    data["item_order"] = data.pop("order", 0)
    _save_item("batch_queue", data)


def load_batch_queue() -> List[QueueItem]:
    """キューアイテムを order 順にソートしてリストでロードします。"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    items: List[QueueItem] = []
    try:
        # item_order でソートして取得
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

        # JSON 文字列 -> Dict 変換処理
        if "actor_assignments" in row_dict and isinstance(
            row_dict["actor_assignments"], str
        ):
            row_dict["actor_assignments"] = json_str_to_dict(
                row_dict["actor_assignments"]
            )
        else:
            row_dict["actor_assignments"] = {}

        # 'item_order' を 'order' にマッピング
        row_dict["order"] = row_dict.pop("item_order", 0)

        try:
            # 存在しないフィールドは無視してインスタンス化
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
