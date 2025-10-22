# src/database.py
import sqlite3
import json
import os
from typing import Dict, List, Type, TypeVar, Any
from .models import (
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
    list_to_json_str,
    json_str_to_list,
)

# Define path relative to this file
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BASE_DIR, "..", "data", "prompt_data.db")

T = TypeVar("T")  # Generic type variable for dataclasses

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Actors Table (using PromptPartBase + Actor specific)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actors (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
            prompt TEXT, negative_prompt TEXT,
            base_costume_id TEXT, base_pose_id TEXT, base_expression_id TEXT,
            work_title TEXT, character_name TEXT
        )""")
    # Scenes Table (complex fields as JSON TEXT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
            prompt_template TEXT, negative_template TEXT,
            background_id TEXT, lighting_id TEXT, composition_id TEXT,
            roles TEXT, role_directions TEXT,
            reference_image_path TEXT, image_mode TEXT
        )""")
    # Directions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS directions (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
            prompt TEXT, negative_prompt TEXT,
            costume_id TEXT, pose_id TEXT, expression_id TEXT
        )""")
    # Simple Parts Tables (e.g., Costumes)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS costumes (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT,
            prompt TEXT, negative_prompt TEXT
        )""")
    # ... Create tables for Pose, Expression, Background, Lighting, Composition similarly ...

    # SD Params Table (Simple Key-Value)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sd_params ( key TEXT PRIMARY KEY, value TEXT )""")

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


# --- Generic Load/Save Functions ---


def _save_item(table_name: str, item_data: Dict[str, Any]):
    """Generic function to insert/replace an item."""
    conn = get_connection()
    cursor = conn.cursor()
    columns = ", ".join(item_data.keys())
    placeholders = ", ".join(["?"] * len(item_data))
    sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
    cursor.execute(sql, list(item_data.values()))
    conn.commit()
    conn.close()


def _load_items(table_name: str, class_type: Type[T]) -> Dict[str, T]:
    """Generic function to load all items of a type."""
    conn = get_connection()
    # Make rows accessible by column name
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:  # Handle case where table might not exist yet
        print(f"Table '{table_name}' not found. Returning empty dictionary.")
        rows = []
    finally:
        conn.close()

    items: Dict[str, T] = {}
    for row in rows:
        row_dict = dict(row)  # Convert sqlite3.Row to dict
        item_id = row_dict.get("id")
        if not item_id:
            continue

        # Handle potential JSON decoding for complex fields if needed by class_type
        # (Scene needs specific handling)
        if class_type == Scene:
            row_dict["tags"] = json.loads(row_dict.get("tags") or "[]")
            row_dict["roles"] = json_str_to_list(row_dict.get("roles"), SceneRole)
            row_dict["role_directions"] = json_str_to_list(
                row_dict.get("role_directions"), RoleDirection
            )
        elif hasattr(class_type, "tags"):  # Handle tags for others
            row_dict["tags"] = json.loads(row_dict.get("tags") or "[]")

        try:
            items[item_id] = class_type(**row_dict)
        except TypeError as e:
            print(f"Error creating {class_type.__name__} from row {row_dict}: {e}")

    return items


def _delete_item(table_name: str, item_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


# --- Specific Save/Load Functions ---


def save_actor(actor: Actor):
    data = actor.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))  # Tags to JSON
    _save_item("actors", data)


def load_actors() -> Dict[str, Actor]:
    return _load_items("actors", Actor)


def delete_actor(actor_id: str):
    _delete_item("actors", actor_id)


def save_scene(scene: Scene):
    data = scene.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    data["roles"] = list_to_json_str(data.get("roles", []))  # List<dataclass> to JSON
    data["role_directions"] = list_to_json_str(data.get("role_directions", []))
    _save_item("scenes", data)


def load_scenes() -> Dict[str, Scene]:
    return _load_items("scenes", Scene)  # Specific handling inside _load_items


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


# --- Save/Load for Simple Parts (Example: Costume) ---
def save_costume(costume: Costume):
    data = costume.__dict__.copy()
    data["tags"] = json.dumps(data.get("tags", []))
    _save_item("costumes", data)


def load_costumes() -> Dict[str, Costume]:
    return _load_items("costumes", Costume)


def delete_costume(costume_id: str):
    _delete_item("costumes", costume_id)


# ... Implement save/load/delete for Pose, Expression, Background, Lighting, Composition similarly ...


# --- SD Params Save/Load ---
def save_sd_params(params: StableDiffusionParams):
    conn = get_connection()
    cursor = conn.cursor()
    for key, value in params.__dict__.items():
        cursor.execute(
            "INSERT OR REPLACE INTO sd_params (key, value) VALUES (?, ?)",
            (key, str(value)),
        )  # Store everything as string
    conn.commit()
    conn.close()


def load_sd_params() -> StableDiffusionParams:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM sd_params")
    rows = cursor.fetchall()
    conn.close()

    params_dict = {key: value for key, value in rows}
    # Convert back to correct types
    return StableDiffusionParams(
        steps=int(params_dict.get("steps", 20)),
        sampler_name=params_dict.get("sampler_name", "Euler a"),
        cfg_scale=float(params_dict.get("cfg_scale", 7.0)),
        seed=int(params_dict.get("seed", -1)),
        width=int(params_dict.get("width", 512)),
        height=int(params_dict.get("height", 512)),
        denoising_strength=float(params_dict.get("denoising_strength", 0.6)),
    )
