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
    Background,
    Lighting,
    Composition,
    Scene,
    SceneRole,
    Style,
    ColorPaletteItem,
    Cut,
    State,
    AdditionalPrompt,
    RoleAppearanceAssignment,
)

ap_quality_up = AdditionalPrompt(
    id="ap_quality_1",
    name="品質向上",
    tags=["quality"],
    prompt="masterpiece, best quality, hires",
    negative_prompt="worst quality, low quality",
)
ap_lens_effect = AdditionalPrompt(
    id="ap_effect_1",
    name="レンズ効果",
    tags=["effect", "camera"],
    prompt="chromatic aberration, lens flare",
    negative_prompt="",
)

state_damaged = State(
    id="state_damaged_1",
    name="破損状態1",
    category="damaged",
    tags=["broken", "torn"],
    prompt="torn clothes, scratches",
    negative_prompt="",
)
state_wet = State(
    id="state_wet_1",
    name="濡れ状態1",
    category="wet",
    tags=["soaked"],
    prompt="wet clothes, dripping water, wet hair",
    negative_prompt="dry",
)
state_casual_clothes = State(
    id="state_casual_1",
    name="私服状態1",
    category="casual",
    tags=["plain clothes"],
    prompt="wearing casual clothes, hoodie, jeans",
    negative_prompt="uniform, dress",
)

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
char_another_a = Character(
    id="char_another_a",
    name="キャラA",
    work_id="work_another",
    tags=[],
    personal_color="green",
    underwear_color="black",
)

default_sd_params: StableDiffusionParams = StableDiffusionParams(
    id="sdp_default_1",
    name="Default (Euler a, 512x512)",
    steps=20,
    sampler_name="Euler a",
    cfg_scale=7.0,
    seed=-1,
    width=512,
    height=512,
    denoising_strength=0.6,
)

style_default = Style(
    id="style_default",
    name="デフォルトスタイル",
    tags=[],
    prompt="",
    negative_prompt="",
)
style_anime = Style(
    id="style_anime",
    name="アニメ風",
    tags=["illustration"],
    prompt="anime style, illustration, high quality",
    negative_prompt="photorealistic, real life",
)

cut_default_solo_1 = Cut(
    id="cut_default_solo_1",
    name="ソロカット1",
    prompt_template="masterpiece, best quality, solo focus, ([R1])",
    negative_template="worst quality, low quality, watermark, signature, multiple people",
    roles=[SceneRole(id="r1", name_in_scene="モデル")],
    reference_image_path="",
    image_mode="txt2img",
)

cut_default_pair_1 = Cut(
    id="cut_default_pair_1",
    name="ペアカット1",
    prompt_template="masterpiece, best quality, ([R1]) and ([R2]), (2 people:1.2)",
    negative_template="worst quality, low quality, watermark, signature, 3 people",
    roles=[
        SceneRole(id="r1", name_in_scene="人物A"),
        SceneRole(id="r2", name_in_scene="人物B"),
    ],
    reference_image_path="path/to/reference.png",
    image_mode="img2img",
)

pose_default_standing = Pose(
    id="pose_default_standing", name="デフォルト立ち", prompt="standing"
)
expr_default_neutral = Expression(id="expr_default_neutral", name="デフォルト無表情")
expr_default_smiling = Expression(
    id="expr_default_smiling", name="デフォルト微笑み", prompt="smiling"
)
costume_default_shirt = Costume(
    id="costume_default_shirt",
    name="デフォルトシャツ",
    prompt="wearing a simple white shirt",
    state_ids=[state_damaged.id, state_wet.id, state_casual_clothes.id],
)
costume_colored_dress = Costume(
    id="costume_colored_dress",
    name="カラードレス",
    prompt="wearing a beautiful [C1] dress, [C2] underwear",
    state_ids=[state_damaged.id],
    color_palette=[
        ColorPaletteItem(placeholder="[C1]", color_ref="personal_color"),
        ColorPaletteItem(placeholder="[C2]", color_ref="underwear_color"),
    ],
)
bg_default_white = Background(
    id="bg_default_white", name="デフォルト白背景", prompt="simple white background"
)
light_default_studio = Lighting(
    id="light_default_studio", name="デフォルトスタジオ照明", prompt="studio lighting"
)
comp_default_medium = Composition(
    id="comp_default_medium", name="デフォルトミディアMショット", prompt="medium shot"
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
        char_another_a.id: char_another_a,
    },
    actors={
        "actor_default_male": Actor(
            id="actor_default_male",
            name="デフォルト男性Actor",
            tags=["male"],
            prompt="1boy, handsome",
            negative_prompt="ugly, deformed",
            character_id="char_default_male",
            base_costume_id="costume_default_shirt",
            base_pose_id="pose_default_standing",
            base_expression_id="expr_default_neutral",
        ),
        "actor_default_female": Actor(
            id="actor_default_female",
            name="デフォルト女性Actor",
            tags=["female"],
            prompt="1girl, beautiful",
            negative_prompt="ugly, deformed",
            character_id="char_default_female",
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
            character_id="char_another_a",
            base_costume_id="costume_default_shirt",
            base_pose_id="pose_default_standing",
            base_expression_id="expr_default_neutral",
        ),
    },
    cuts={
        cut_default_solo_1.id: cut_default_solo_1,
        cut_default_pair_1.id: cut_default_pair_1,
    },
    costumes={
        "costume_default_shirt": costume_default_shirt,
        "costume_colored_dress": costume_colored_dress,
    },
    poses={
        "pose_default_standing": pose_default_standing,
    },
    expressions={
        "expr_default_neutral": expr_default_neutral,
        "expr_default_smiling": expr_default_smiling,
    },
    backgrounds={
        "bg_default_white": bg_default_white,
    },
    lighting={
        "light_default_studio": light_default_studio,
    },
    compositions={
        "comp_default_medium": comp_default_medium,
    },
    # --- ▼▼▼ scenes 辞書の定義を置き換え ▼▼▼ ---
    scenes={
        "scene_default_solo": Scene(
            id="scene_default_solo",
            name="デフォルトソロシーン",
            tags=["solo"],
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_ids=[comp_default_medium.id],  # ★ 変更
            cut_id=cut_default_solo_1.id,
            role_assignments=[
                RoleAppearanceAssignment(
                    role_id="r1",
                    costume_ids=[costume_default_shirt.id],
                    pose_ids=[pose_default_standing.id],
                    expression_ids=[expr_default_neutral.id],
                )
            ],
            style_id=style_default.id,
            sd_param_id=default_sd_params.id,
            state_categories=["damaged"],
            additional_prompt_ids=[ap_quality_up.id],
        ),
        "scene_default_pair": Scene(
            id="scene_default_pair",
            name="デフォルトペアシーン",
            tags=["pair"],
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_ids=[comp_default_medium.id],  # ★ 変更
            cut_id=cut_default_pair_1.id,
            role_assignments=[
                RoleAppearanceAssignment(
                    role_id="r1",
                    costume_ids=[costume_default_shirt.id],
                    pose_ids=[pose_default_standing.id],
                    expression_ids=[
                        expr_default_neutral.id,
                        expr_default_smiling.id,
                    ],
                ),
                RoleAppearanceAssignment(
                    role_id="r2",
                    costume_ids=[
                        costume_colored_dress.id,
                        costume_default_shirt.id,
                    ],
                    pose_ids=[pose_default_standing.id],
                    expression_ids=[expr_default_smiling.id],
                ),
            ],
            style_id=style_anime.id,
            sd_param_id=default_sd_params.id,
            state_categories=["wet", "damaged"],
            additional_prompt_ids=[ap_quality_up.id, ap_lens_effect.id],
        ),
        "scene_no_state": Scene(
            id="scene_no_state",
            name="状態カテゴリなしシーン",
            tags=["solo"],
            composition_ids=[comp_default_medium.id],  # ★ 変更
            cut_id=cut_default_solo_1.id,
            role_assignments=[RoleAppearanceAssignment(role_id="r1")],
            style_id=style_default.id,
            sd_param_id=default_sd_params.id,
            state_categories=[],
            additional_prompt_ids=[],
        ),
        "scene_casual": Scene(
            id="scene_casual_solo",
            name="私服ソロシーン",
            tags=["solo", "casual"],
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_ids=[comp_default_medium.id],  # ★ 変更
            cut_id=cut_default_solo_1.id,
            role_assignments=[RoleAppearanceAssignment(role_id="r1")],
            style_id=style_anime.id,
            sd_param_id=default_sd_params.id,
            state_categories=["casual"],
            additional_prompt_ids=[ap_quality_up.id],
        ),
    },
    # --- ▲▲▲ 置き換えここまで ▲▲▲ ---
    styles={
        style_default.id: style_default,
        style_anime.id: style_anime,
    },
    sdParams={default_sd_params.id: default_sd_params},
    states={
        state_damaged.id: state_damaged,
        state_wet.id: state_wet,
        state_casual_clothes.id: state_casual_clothes,
    },
    additional_prompts={
        ap_quality_up.id: ap_quality_up,
        ap_lens_effect.id: ap_lens_effect,
    },
)
