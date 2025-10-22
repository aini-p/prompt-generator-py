# src/models.py
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, TypeAlias


# --- ベースオブジェクト ---
@dataclass
class PromptPartBase:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    prompt: str = ""
    negative_prompt: str = ""


# --- Level 1: ライブラリ (基本パーツ) ---
@dataclass
class Costume(PromptPartBase):
    pass


@dataclass
class Pose(PromptPartBase):
    pass


@dataclass
class Expression(PromptPartBase):
    pass


@dataclass
class Background(PromptPartBase):
    pass


@dataclass
class Lighting(PromptPartBase):
    pass


@dataclass
class Composition(PromptPartBase):
    pass


@dataclass
class Actor(PromptPartBase):
    base_costume_id: str = ""
    base_pose_id: str = ""
    base_expression_id: str = ""
    work_title: str = ""
    character_name: str = ""


@dataclass
class Direction(PromptPartBase):
    costume_id: Optional[str] = None
    pose_id: Optional[str] = None
    expression_id: Optional[str] = None


# --- Level 3: Scene (シーン・テンプレート) ---
@dataclass
class SceneRole:
    id: str  # プレイスホルダーID (例: "r1", "r2")
    name_in_scene: str  # 編集可能な表示名 (例: "主人公")


@dataclass
class RoleDirection:
    role_id: str  # "r1"
    direction_ids: List[str] = field(
        default_factory=list
    )  # ["dir_Smiling", "dir_Waving"]


@dataclass
class Scene:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    prompt_template: str = ""
    negative_template: str = ""
    background_id: str = ""
    lighting_id: str = ""
    composition_id: str = ""
    roles: List[SceneRole] = field(default_factory=list)
    role_directions: List[RoleDirection] = field(default_factory=list)
    reference_image_path: str = ""
    image_mode: str = "txt2img"  # "txt2img" | "img2img" | "img2img_polish"


# --- Stable Diffusion パラメータ ---
@dataclass
class StableDiffusionParams:
    steps: int = 20
    sampler_name: str = "Euler a"
    cfg_scale: float = 7.0
    seed: int = -1
    width: int = 512
    height: int = 512
    denoising_strength: float = 0.6


# --- tasks.json 用 ---
@dataclass
class ImageGenerationTask:
    prompt: str
    negative_prompt: str
    steps: int
    sampler_name: str
    cfg_scale: float
    seed: int
    width: int
    height: int
    mode: str
    filename_prefix: str
    source_image_path: str
    denoising_strength: Optional[float]  # None or float


# --- プロンプト生成結果の型 ---
@dataclass
class GeneratedPrompt:
    cut: int
    name: str
    positive: str
    negative: str
    firstActorInfo: Optional[Dict[str, str]] = (
        None  # {"work_title": "...", "character_name": "..."}
    )


# --- DB全体の構造 (Type Hinting用) ---
@dataclass
class FullDatabase:
    actors: Dict[str, Actor] = field(default_factory=dict)
    costumes: Dict[str, Costume] = field(default_factory=dict)
    poses: Dict[str, Pose] = field(default_factory=dict)
    expressions: Dict[str, Expression] = field(default_factory=dict)
    directions: Dict[str, Direction] = field(default_factory=dict)
    backgrounds: Dict[str, Background] = field(default_factory=dict)
    lighting: Dict[str, Lighting] = field(default_factory=dict)
    compositions: Dict[str, Composition] = field(default_factory=dict)
    scenes: Dict[str, Scene] = field(default_factory=dict)
    sdParams: StableDiffusionParams = field(default_factory=StableDiffusionParams)


# --- Helper functions ---
def list_to_json_str(data_list: List[Any]) -> str:
    # Check if items are dataclasses before accessing __dict__
    return json.dumps(
        [item.__dict__ if hasattr(item, "__dict__") else item for item in data_list]
    )


def json_str_to_list(json_str: Optional[str], class_type: type) -> List[Any]:
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        if callable(class_type):
            return [class_type(**item) for item in data if isinstance(item, dict)]
        else:
            print(f"Warning: class_type {class_type} is not callable for JSON list.")
            return data
    except json.JSONDecodeError:
        print(
            f"Error decoding JSON for {getattr(class_type, '__name__', class_type)}: {json_str}"
        )
        return []
    except TypeError as e:
        print(
            f"Error creating instance of {getattr(class_type, '__name__', class_type)}: {e}. JSON: {json_str}"
        )
        return []


# --- ★★★ STORAGE_KEYS 定義 (ここにあるか確認) ★★★ ---
STORAGE_KEYS: Dict[str, str] = {
    "actors": "promptBuilder_actors",
    "costumes": "promptBuilder_costumes",
    "poses": "promptBuilder_poses",
    "expressions": "promptBuilder_expressions",
    "directions": "promptBuilder_directions",
    "backgrounds": "promptBuilder_backgrounds",
    "lighting": "promptBuilder_lighting",
    "compositions": "promptBuilder_compositions",
    "scenes": "promptBuilder_scenes",
    "sdParams": "promptBuilder_sdParams",
}

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
