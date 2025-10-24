# src/data/mocks.py
from src.models import (
    Work,
    Character,
    FullDatabase,
    StableDiffusionParams,
    Actor,
    Costume,
    Pose,
    Expression,
    Direction,
    Background,
    Lighting,
    Composition,
    Scene,
    SceneRole,
    RoleDirection,
    Style,
    ColorPaletteItem,
)

# --- ★ Work モックデータ ---
work_default = Work(
    id="work_default",
    title_jp="デフォルト作品",
    title_en="Default Work",
    tags=["sample"],
    sns_tags="#DefaultWork",
)
work_another = Work(
    id="work_another",
    title_jp="別作品",
    title_en="Another Work",
    tags=["test"],
    sns_tags="#AnotherWork",
)

# --- ★ Character モックデータ ---
char_default_male = Character(
    id="char_default_male",
    name="デフォルト男性キャラ",
    work_id="work_default",
    tags=["protagonist"],
    personal_color="blue",
    underwear_color="white",
)
char_default_female = Character(
    id="char_default_female",
    name="デフォルト女性キャラ",
    work_id="work_default",
    tags=["heroine"],
    personal_color="pink",
    underwear_color="lace",
)
# --- デフォルトの Stable Diffusion パラメータ ---
default_sd_params: StableDiffusionParams = StableDiffusionParams(
    steps=20,
    sampler_name="Euler a",
    cfg_scale=7.0,
    seed=-1,
    width=512,
    height=512,
    denoising_strength=0.6,
)
# --- ★ Style モックデータ ---
style_default = Style(
    id="style_default",
    name="Default Style",
    tags=[],
    prompt="masterpiece, best quality,",
    negative_prompt="worst quality, low quality,",
)
style_anime = Style(
    id="style_anime",
    name="Anime Style",
    tags=["anime"],
    prompt="anime style, vibrant colors,",
    negative_prompt="photorealistic, real life,",
)

# --- アプリケーション全体の初期データベース ---
initialMockDatabase: FullDatabase = FullDatabase(
    works={
        work_default.id: work_default,
        work_another.id: work_another,
    },
    characters={
        char_default_male.id: char_default_male,
        char_default_female.id: char_default_female,
    },
    actors={
        "actor_default_male": Actor(
            id="actor_default_male",
            name="デフォルト男性Actor",  # Actor 名と Character 名は別
            tags=["male"],
            prompt="1boy, handsome",
            negative_prompt="ugly, deformed",
            character_id="char_default_male",  # character_id を指定
            base_costume_id="costume_default_shirt",
            base_pose_id="pose_default_standing",
            base_expression_id="expr_default_neutral",
            # work_title, character_name は削除
        ),
        "actor_default_female": Actor(
            id="actor_default_female",
            name="デフォルト女性Actor",
            tags=["female"],
            prompt="1girl, beautiful",
            negative_prompt="ugly, deformed",
            character_id="char_default_female",  # character_id を指定
            base_costume_id="costume_default_shirt",
            base_pose_id="pose_default_standing",
            base_expression_id="expr_default_neutral",
        ),
        "actor_another_a": Actor(
            id="actor_another_a",
            name="キャラA Actor",
            tags=["male"],
            prompt="1boy",
            negative_prompt="",
            character_id="char_another_a",  # character_id を指定
            base_costume_id="costume_default_shirt",
            base_pose_id="pose_default_standing",
            base_expression_id="expr_default_neutral",
        ),
    },
    # --- 衣装 (Costumes) ---
    costumes={
        "costume_default_shirt": Costume(
            id="costume_default_shirt",
            name="デフォルトシャツ",
            tags=[],
            prompt="wearing a simple white shirt",
            negative_prompt="",
            # color_placeholders={} を color_palette=[] に変更
            color_palette=[],
        ),
        "costume_colored_dress": Costume(
            id="costume_colored_dress",
            name="カラードレス",
            tags=["dress"],
            prompt="wearing a beautiful [C1] dress, [C2] underwear",
            negative_prompt="",
            # color_placeholders={...} を color_palette=[...] に変更
            color_palette=[
                ColorPaletteItem(placeholder="[C1]", color_ref="personal_color"),
                ColorPaletteItem(placeholder="[C2]", color_ref="underwear_color"),
            ],
        ),
    },
    # --- ポーズ (Poses) ---
    poses={
        "pose_default_standing": Pose(
            id="pose_default_standing",
            name="デフォルト立ち",
            tags=[],
            prompt="standing",
            negative_prompt="",
        )
    },
    # --- 表情 (Expressions) ---
    expressions={
        "expr_default_neutral": Expression(
            id="expr_default_neutral",
            name="デフォルト無表情",
            tags=[],
            prompt="neutral expression",
            negative_prompt="smiling, laughing",
        )
    },
    # --- 演出 (Directions) ---
    directions={
        "dir_default_base": Direction(
            id="dir_default_base",
            name="演出: 基本状態",
            tags=[],
            prompt="",
            negative_prompt="",
        ),
        "dir_default_smile": Direction(
            id="dir_default_smile",
            name="演出: 微笑む",
            tags=[],
            expression_id="expr_default_smiling",
            prompt="smiling",
            negative_prompt="",
        ),
    },
    # --- 背景 (Backgrounds) ---
    backgrounds={
        "bg_default_white": Background(
            id="bg_default_white",
            name="デフォルト白背景",
            tags=[],
            prompt="simple white background",
            negative_prompt="detailed background, scenery",
        )
    },
    # --- 照明 (Lighting) ---
    lighting={
        "light_default_studio": Lighting(
            id="light_default_studio",
            name="デフォルトスタジオ照明",
            tags=[],
            prompt="studio lighting",
            negative_prompt="dark, night",
        )
    },
    # --- 構図 (Compositions) ---
    compositions={
        "comp_default_medium": Composition(
            id="comp_default_medium",
            name="デフォルトミディアムショット",
            tags=[],
            prompt="medium shot",
            negative_prompt="",
        )
    },
    # --- シーン (Scenes) ---
    scenes={
        "scene_default_solo": Scene(
            id="scene_default_solo",
            name="デフォルトソロシーン",
            tags=["solo"],
            prompt_template="masterpiece, best quality, solo focus, ([R1])",
            negative_template="worst quality, low quality, watermark, signature, multiple people",
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_id="comp_default_medium",
            roles=[SceneRole(id="r1", name_in_scene="モデル")],
            role_directions=[
                RoleDirection(role_id="r1", direction_ids=["dir_default_base"])
            ],  # 基本状態のみ
            reference_image_path="",
            image_mode="txt2img",
        ),
        "scene_default_pair": Scene(
            id="scene_default_pair",
            name="デフォルトペアシーン",
            tags=["pair"],
            prompt_template="masterpiece, best quality, ([R1]) and ([R2]), (2 people:1.2)",
            negative_template="worst quality, low quality, watermark, signature, 3 people",
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_id="comp_default_medium",
            roles=[
                SceneRole(id="r1", name_in_scene="人物A"),
                SceneRole(id="r2", name_in_scene="人物B"),
            ],
            role_directions=[
                RoleDirection(role_id="r1", direction_ids=["dir_default_base"]),
                RoleDirection(
                    role_id="r2", direction_ids=["dir_default_smile"]
                ),  # 片方だけ微笑む
            ],
            reference_image_path="",
            image_mode="txt2img",
        ),
    },
    styles={
        style_default.id: style_default,
        style_anime.id: style_anime,
    },
    # --- SDパラメータ ---
    sdParams=default_sd_params,
)

# (必要に応じて、expr_default_smiling など、Directionで参照しているパーツも上記に追加してください)
# 例:
initialMockDatabase.expressions["expr_default_smiling"] = Expression(
    id="expr_default_smiling",
    name="デフォルト微笑み",
    tags=[],
    prompt="smiling",
    negative_prompt="",
)
