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
    Cut,  # ★ Cut をインポート
)

# --- Work モックデータ ---
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

# --- Character モックデータ ---
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

# --- ▼▼▼ デフォルトの SD Params に id と name を追加 ▼▼▼ ---
default_sd_params: StableDiffusionParams = StableDiffusionParams(
    id="sdp_default_1",  # ★ ID を追加
    name="Default (Euler a, 512x512)",  # ★ 名前を追加
    steps=20,
    sampler_name="Euler a",
    cfg_scale=7.0,
    seed=-1,
    width=512,
    height=512,
    denoising_strength=0.6,
)
# --- ▲▲▲ 修正ここまで ▲▲▲ ---

# --- Style モックデータ ---
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

# --- ▼▼▼ Cut モックデータを作成 ▼▼▼ ---
cut_default_solo_1 = Cut(
    id="cut_default_solo_1",
    name="ソロカット1",
    prompt_template="masterpiece, best quality, solo focus, ([R1])",
    negative_template="worst quality, low quality, watermark, signature, multiple people",
    roles=[SceneRole(id="r1", name_in_scene="モデル")],
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
)
# --- ▲▲▲ 追加ここまで ▲▲▲ ---


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
    # --- ▼▼▼ cuts 辞書を追加 ▼▼▼ ---
    cuts={
        cut_default_solo_1.id: cut_default_solo_1,
        cut_default_pair_1.id: cut_default_pair_1,
    },
    # --- ▲▲▲ 追加ここまで ▲▲▲ ---
    costumes={
        "costume_default_shirt": Costume(
            id="costume_default_shirt",
            name="デフォルトシャツ",
            tags=[],
            prompt="wearing a simple white shirt",
            negative_prompt="",
            color_palette=[],
        ),
        "costume_colored_dress": Costume(
            id="costume_colored_dress",
            name="カラードレス",
            tags=["dress"],
            prompt="wearing a beautiful [C1] dress, [C2] underwear",
            negative_prompt="",
            color_palette=[
                ColorPaletteItem(placeholder="[C1]", color_ref="personal_color"),
                ColorPaletteItem(placeholder="[C2]", color_ref="underwear_color"),
            ],
        ),
    },
    poses={
        "pose_default_standing": Pose(
            id="pose_default_standing",
            name="デフォルト立ち",
            tags=[],
            prompt="standing",
            negative_prompt="",
        )
    },
    expressions={
        "expr_default_neutral": Expression(
            id="expr_default_neutral",
            name="デフォルト無表情",
            tags=[],
            prompt="",
            negative_prompt="",
        ),
        # expr_default_smiling は後で追加
    },
    directions={
        "dir_default_base": Direction(
            id="dir_default_base",
            name="デフォルト基本状態",
            tags=[],
            prompt="",
            negative_prompt="",
            costume_id=None,
            pose_id=None,
            expression_id=None,
        ),
        "dir_default_smile": Direction(
            id="dir_default_smile",
            name="デフォルト微笑み",
            tags=["smile"],
            prompt="",
            negative_prompt="",
            costume_id=None,
            pose_id=None,
            expression_id="expr_default_smiling",  # 微笑み表情を上書き
        ),
    },
    backgrounds={
        "bg_default_white": Background(
            id="bg_default_white",
            name="デフォルト白背景",
            tags=[],
            prompt="simple white background",
            negative_prompt="outdoors, indoors",
        )
    },
    lighting={
        "light_default_studio": Lighting(
            id="light_default_studio",
            name="デフォルトスタジオ照明",
            tags=[],
            prompt="studio lighting",
            negative_prompt="",
        )
    },
    compositions={
        "comp_default_medium": Composition(
            id="comp_default_medium",
            name="デフォルトミディアムショット",
            tags=[],
            prompt="medium shot",
            negative_prompt="close-up, long shot",
        )
    },
    # --- ▼▼▼ scenes の定義を修正 (cut_id を使用) ▼▼▼ ---
    scenes={
        "scene_default_solo": Scene(
            id="scene_default_solo",
            name="デフォルトソロシーン",
            tags=["solo"],
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_id="comp_default_medium",
            cut_id=cut_default_solo_1.id,  # ★ Cut の ID を設定
            role_directions=[  # これは Scene に残る
                RoleDirection(role_id="r1", direction_ids=["dir_default_base"])
            ],
            reference_image_path="",
            image_mode="txt2img",
        ),
        "scene_default_pair": Scene(
            id="scene_default_pair",
            name="デフォルトペアシーン",
            tags=["pair"],
            background_id="bg_default_white",
            lighting_id="light_default_studio",
            composition_id="comp_default_medium",
            cut_id=cut_default_pair_1.id,  # ★ Cut の ID を設定
            role_directions=[  # これは Scene に残る
                RoleDirection(role_id="r1", direction_ids=["dir_default_base"]),
                RoleDirection(role_id="r2", direction_ids=["dir_default_smile"]),
            ],
            reference_image_path="",
            image_mode="txt2img",
        ),
    },
    # --- ▲▲▲ 修正ここまで ▲▲▲ ---
    styles={
        style_default.id: style_default,
        style_anime.id: style_anime,
    },
    # --- ▼▼▼ SDパラメータを辞書型に変更 ▼▼▼ ---
    sdParams={default_sd_params.id: default_sd_params},
    # --- ▲▲▲ 修正ここまで ▲▲▲ ---
)

# --- expr_default_smiling の追加 ---
initialMockDatabase.expressions["expr_default_smiling"] = Expression(
    id="expr_default_smiling",
    name="デフォルト微笑み",
    tags=[],
    prompt="smiling",
    negative_prompt="",
)
