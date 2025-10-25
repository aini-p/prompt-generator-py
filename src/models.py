# src/models.py
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, TypeAlias


# --- ★ Work と Character を追加 ---
@dataclass
class Work:
    id: str
    title_jp: str = ""
    title_en: str = ""
    tags: List[str] = field(default_factory=list)
    sns_tags: str = ""  # カンマ区切り想定


# --- ★ カラーパレット項目 データクラス ---
@dataclass
class ColorPaletteItem:
    placeholder: str = "[C1]"
    color_ref: str = "personal_color"  # デフォルト値も文字列に


@dataclass
class Character:
    id: str
    name: str = ""
    work_id: str = ""  # 対応する Work の ID
    tags: List[str] = field(
        default_factory=list
    )  # キャラクター固有のタグ（オプション）
    personal_color: str = ""  # 例: "blue"
    underwear_color: str = ""  # 例: "white"


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


# --- Level 2: Actor, Direction ---
@dataclass
class Actor(PromptPartBase):
    # --- ★ work_title, character_name を削除し、character_id を追加 ---
    character_id: str = ""  # 対応する Character の ID
    # --- ★ 削除ここまで ---
    base_costume_id: str = ""
    base_pose_id: str = ""
    base_expression_id: str = ""
    # work_title: str = "" # 削除
    # character_name: str = "" # 削除


@dataclass
class Direction(PromptPartBase):
    costume_id: Optional[str] = None
    pose_id: Optional[str] = None
    expression_id: Optional[str] = None


# --- Level 3: Scene (シーン・テンプレート) ---
@dataclass
class SceneRole:
    id: str
    name_in_scene: str


@dataclass
class Cut:
    id: str
    name: str = ""  # カット名 (オプション)
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
    cut_id: Optional[str] = None
    role_directions: List[RoleDirection] = field(
        default_factory=list
    )  # これは Scene が持つ
    reference_image_path: str = ""
    image_mode: str = "txt2img"


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
    denoising_strength: Optional[float]


# --- プロンプト生成結果の型 ---
@dataclass
class GeneratedPrompt:
    cut: int
    name: str
    positive: str
    negative: str
    # ★ firstActorInfo の型を変更 (Character と Work を含める)
    firstActorInfo: Optional[Dict[str, Any]] = None
    # 例: {"character": Character(...), "work": Work(...)}


# --- ★ DB全体の構造に Work と Character を追加 ---
@dataclass
class FullDatabase:
    works: Dict[str, Work] = field(default_factory=dict)  # 追加
    characters: Dict[str, Character] = field(default_factory=dict)  # 追加
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
    sdParams: StableDiffusionParams = field(default_factory=StableDiffusionParams)


# --- Helper functions ---
def list_to_json_str(data_list: List[Any]) -> str:
    return json.dumps(
        [item.__dict__ if hasattr(item, "__dict__") else item for item in data_list]
    )


def json_str_to_list(json_str: Optional[str], class_type: type) -> List[Any]:
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        if callable(class_type):
            # リスト内の各辞書に対してクラスをインスタンス化
            # ここで **item が失敗する場合、item が辞書でない可能性がある
            return [class_type(**item) for item in data if isinstance(item, dict)]
        else:
            print(f"Warning: class_type {class_type} is not callable for JSON list.")
            return data  # 変換せずにそのまま返す
    except json.JSONDecodeError:
        print(
            f"Error decoding JSON for {getattr(class_type, '__name__', class_type)}: {json_str}"
        )
        return []
    except TypeError as e:
        # **item でインスタンス化しようとした際に、予期せぬキーや型があると発生
        print(
            f"Error creating instance of {getattr(class_type, '__name__', class_type)}: {e}. JSON part: {json_str[:100]}..."
        )  # エラー箇所特定のため一部表示
        # エラーが発生した要素を除外してリストを作成する試み（オプション）
        valid_items = []
        try:
            data = json.loads(json_str)
            for item in data:
                if isinstance(item, dict):
                    try:
                        valid_items.append(class_type(**item))
                    except TypeError:
                        print(f"  Skipping item due to TypeError: {item}")
        except:
            pass  # 二次的なエラーは無視
        return valid_items
        # return [] # または、エラー時は空リストを返す


# --- ★ STORAGE_KEYS に Work と Character を追加 ---
STORAGE_KEYS: Dict[str, str] = {
    "works": "promptBuilder_works",  # 追加
    "characters": "promptBuilder_characters",  # 追加
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

# --- ★ DatabaseKey に Work と Character を追加 ---
DatabaseKey = Literal[
    "works",  # 追加
    "characters",  # 追加
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
