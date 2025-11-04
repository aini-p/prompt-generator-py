# src/models.py
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, TypeAlias


@dataclass
class State:  # PromptPartBase を継承しない独立したクラス
    id: str
    name: str
    category: str = ""  # 状態カテゴリ (例: "damaged", "wet", "casual")
    tags: List[str] = field(default_factory=list)  # オプションのタグ
    prompt: str = ""
    negative_prompt: str = ""


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
class AdditionalPrompt(PromptPartBase):
    pass  # PromptPartBase と同じ属性を持つ


@dataclass
class Costume(PromptPartBase):
    color_palette: List[ColorPaletteItem] = field(default_factory=list)
    state_ids: List[str] = field(default_factory=list)


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
    reference_image_path: str = ""
    image_mode: str = "txt2img"


@dataclass
class RoleAppearanceAssignment:
    role_id: str  # SceneRole.id に対応
    costume_ids: List[str] = field(default_factory=list)
    pose_ids: List[str] = field(default_factory=list)
    expression_ids: List[str] = field(default_factory=list)


@dataclass
class Scene:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    background_id: str = ""
    lighting_id: str = ""
    composition_ids: List[str] = field(default_factory=list)  # ★ 変更 (id -> ids)
    cut_id: Optional[str] = None
    role_assignments: List[RoleAppearanceAssignment] = field(default_factory=list)
    style_id: Optional[str] = None
    sd_param_id: Optional[str] = None
    state_categories: List[str] = field(default_factory=list)
    additional_prompt_ids: List[str] = field(default_factory=list)


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


@dataclass
class BatchMetadata:
    """
    tasks.json に含めるメタデータ。
    """

    sequence_name: str = ""
    scene_name: str = ""
    character_names: List[str] = field(default_factory=list)
    work_titles: List[str] = field(default_factory=list)


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
    metadata: BatchMetadata = field(default_factory=BatchMetadata)


# --- プロンプト生成結果の型 (変更なし) ---
@dataclass
class GeneratedPrompt:
    cut: int
    name: str
    positive: str
    negative: str
    firstActorInfo: Optional[Dict[str, Any]] = None


@dataclass
class SequenceSceneEntry:
    scene_id: str
    is_enabled: bool = True
    # order: int = 0 # 順序はリストのインデックスで管理


@dataclass
class Sequence:
    id: str
    name: str
    scene_entries: List[SequenceSceneEntry] = field(default_factory=list)


@dataclass
class QueueItem:
    id: str  # キューアイテム自体の一意なID (例: queue_item_timestamp)
    sequence_id: str
    actor_assignments: Dict[str, str] = field(default_factory=dict)
    # (キーが存在しない、または値が "default" の場合はオーバーライドしない)
    appearance_overrides: Dict[str, Dict[str, Optional[str]]] = field(
        default_factory=dict
    )
    order: int = 0  # キュー内での順序
    # status: str = "pending" # オプション: 実行状態


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
    backgrounds: Dict[str, Background] = field(default_factory=dict)
    lighting: Dict[str, Lighting] = field(default_factory=dict)
    compositions: Dict[str, Composition] = field(default_factory=dict)
    scenes: Dict[str, Scene] = field(default_factory=dict)
    styles: Dict[str, Style] = field(default_factory=dict)
    sdParams: Dict[str, StableDiffusionParams] = field(default_factory=dict)
    sequences: Dict[str, Sequence] = field(default_factory=dict)
    states: Dict[str, State] = field(default_factory=dict)
    additional_prompts: Dict[str, AdditionalPrompt] = field(default_factory=dict)


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
    "backgrounds": "promptBuilder_backgrounds",
    "lighting": "promptBuilder_lighting",
    "compositions": "promptBuilder_compositions",
    "scenes": "promptBuilder_scenes",
    "styles": "promptBuilder_styles",
    "sdParams": "promptBuilder_sdParams",
    "states": "promptBuilder_states",
    "additional_prompts": "promptBuilder_additional_prompts",
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
    "backgrounds",
    "lighting",
    "compositions",
    "scenes",
    "styles",
    "sdParams",
    "sequences",
    "states",
    "additional_prompts",
]
