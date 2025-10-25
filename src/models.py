# src/models.py
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, TypeAlias


# --- (Work, ColorPaletteItem, Character, PromptPartBase, Costume, Pose, Expression, Background, Lighting, Composition, Style, Actor, Direction, SceneRole, Cut, RoleDirection, Scene は変更なし) ---
@dataclass
class Work:
    id: str
    title_jp: str = ""
    title_en: str = ""
    tags: List[str] = field(default_factory=list)
    sns_tags: str = ""


@dataclass
class ColorPaletteItem:
    placeholder: str = "[C1]"
    color_ref: str = "personal_color"


@dataclass
class Character:
    id: str
    name: str = ""
    work_id: str = ""
    tags: List[str] = field(default_factory=list)
    personal_color: str = ""
    underwear_color: str = ""


@dataclass
class PromptPartBase:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    prompt: str = ""
    negative_prompt: str = ""


@dataclass
class Costume(PromptPartBase):
    color_palette: List[ColorPaletteItem] = field(default_factory=list)


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
class Style(PromptPartBase):
    pass


@dataclass
class Actor(PromptPartBase):
    character_id: str = ""
    base_costume_id: str = ""
    base_pose_id: str = ""
    base_expression_id: str = ""


@dataclass
class Direction(PromptPartBase):
    costume_id: Optional[str] = None
    pose_id: Optional[str] = None
    expression_id: Optional[str] = None


@dataclass
class SceneRole:
    id: str
    name_in_scene: str


@dataclass
class Cut:
    id: str
    name: str = ""
    prompt_template: str = ""
    negative_template: str = ""
    roles: List[SceneRole] = field(default_factory=list)


@dataclass
class RoleDirection:
    role_id: str
    direction_ids: List[str] = field(default_factory=list)


@dataclass
class Scene:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    background_id: str = ""
    lighting_id: str = ""
    composition_id: str = ""
    cut_id: Optional[str] = None  # ★ cut_id に変更済み
    role_directions: List[RoleDirection] = field(default_factory=list)
    reference_image_path: str = ""
    image_mode: str = "txt2img"


# --- ▼▼▼ StableDiffusionParams を修正 ▼▼▼ ---
@dataclass
class StableDiffusionParams:
    id: str  # ★ ID を追加
    name: str  # ★ 名前を追加
    steps: int = 20
    sampler_name: str = "Euler a"
    cfg_scale: float = 7.0
    seed: int = -1
    width: int = 512
    height: int = 512
    denoising_strength: float = 0.6


# --- ▲▲▲ 修正ここまで ▲▲▲ ---


# --- tasks.json 用 (変更なし) ---
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
    denoising_strength: Optional[float]


# --- プロンプト生成結果の型 (変更なし) ---
@dataclass
class GeneratedPrompt:
    cut: int
    name: str
    positive: str
    negative: str
    firstActorInfo: Optional[Dict[str, Any]] = None


# --- ▼▼▼ FullDatabase を修正 ▼▼▼ ---
@dataclass
class FullDatabase:
    works: Dict[str, Work] = field(default_factory=dict)
    characters: Dict[str, Character] = field(default_factory=dict)
    actors: Dict[str, Actor] = field(default_factory=dict)
    cuts: Dict[str, Cut] = field(default_factory=dict)
    costumes: Dict[str, Costume] = field(default_factory=dict)
    poses: Dict[str, Pose] = field(default_factory=dict)
    expressions: Dict[str, Expression] = field(default_factory=dict)
    directions: Dict[str, Direction] = field(default_factory=dict)
    backgrounds: Dict[str, Background] = field(default_factory=dict)
    lighting: Dict[str, Lighting] = field(default_factory=dict)
    compositions: Dict[str, Composition] = field(default_factory=dict)
    scenes: Dict[str, Scene] = field(default_factory=dict)
    styles: Dict[str, Style] = field(default_factory=dict)
    # ★ sdParams を Dict 型に変更
    sdParams: Dict[str, StableDiffusionParams] = field(default_factory=dict)


# --- ▲▲▲ 修正ここまで ▲▲▲ ---


# --- Helper functions (変更なし) ---
# ... (list_to_json_str, json_str_to_list) ...


# --- STORAGE_KEYS (変更なし) ---
STORAGE_KEYS: Dict[str, str] = {
    "works": "promptBuilder_works",
    "characters": "promptBuilder_characters",
    "actors": "promptBuilder_actors",
    "cuts": "promptBuilder_cuts",
    "costumes": "promptBuilder_costumes",
    "poses": "promptBuilder_poses",
    "expressions": "promptBuilder_expressions",
    "directions": "promptBuilder_directions",
    "backgrounds": "promptBuilder_backgrounds",
    "lighting": "promptBuilder_lighting",
    "compositions": "promptBuilder_compositions",
    "scenes": "promptBuilder_scenes",
    "styles": "promptBuilder_styles",
    "sdParams": "promptBuilder_sdParams",
}

# --- DatabaseKey (変更なし) ---
DatabaseKey = Literal[
    "works",
    "characters",
    "actors",
    "cuts",
    "costumes",
    "poses",
    "expressions",
    "directions",
    "backgrounds",
    "lighting",
    "compositions",
    "scenes",
    "styles",
    "sdParams",
]
