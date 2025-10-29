# src/prompt_generator.py
import itertools
import re
from typing import Dict, List, Optional, Tuple, Mapping, TypeVar, Iterable, Any
from .models import (
    FullDatabase,
    GeneratedPrompt,
    PromptPartBase,
    Actor,
    Cut,
    Scene,
    StableDiffusionParams,
    ImageGenerationTask,
    SceneRole,
    Work,
    Character,
    Costume,
    Pose,
    Expression,
    Style,
    State,
    AdditionalPrompt,
    RoleAppearanceAssignment,  # ★ 追加
)

ActorAssignments = Mapping[str, str]  # Key: role.id, Value: actor.id
T = TypeVar("T")

# ==============================================================================
# Helper Functions
# ==============================================================================


def getCartesianProduct(arrays: Iterable[Iterable[T]]) -> List[List[T]]:
    """ユーティリティ: 配列の直積（デカルト積）を計算する"""
    pools = [list(pool) for pool in arrays if pool]
    if not pools:
        return [[]]
    # itertools.product はタプルのイテレータを返すのでリストのリストに変換
    return [list(item) for item in itertools.product(*pools)]


def _apply_color_palette(
    text: str, costume: Optional[Costume], character: Optional[Character]
) -> str:
    """プロンプト文字列にカラーパレット置換を適用"""
    if not costume or not character or not costume.color_palette or not text:
        return text
    result_text = text
    replacements = {}
    for item in costume.color_palette:
        placeholder = item.placeholder
        attr_name = item.color_ref
        if hasattr(character, attr_name):
            color_value = getattr(character, attr_name, "")
            if color_value:
                replacements[placeholder] = color_value
    sorted_placeholders = sorted(replacements.keys(), key=len, reverse=True)
    for ph in sorted_placeholders:
        result_text = result_text.replace(ph, replacements[ph])
    # 残ったプレイスホルダー削除 (オプション)
    # for item in costume.color_palette:
    #     result_text = result_text.replace(item.placeholder, "")
    return result_text


def _apply_state_prompts(
    base_prompt: str,
    base_negative: str,
    costume: Optional[Costume],
    scene: Scene,
    db: FullDatabase,
) -> Tuple[str, str]:
    """Costumeプロンプトに Scene に合致する State プロンプトを追記"""
    if not costume or not hasattr(costume, "state_ids"):
        return base_prompt, base_negative

    final_prompt = base_prompt
    final_negative = base_negative
    applicable_states: List[State] = []
    scene_categories = set(getattr(scene, "state_categories", []))

    if scene_categories:
        costume_state_ids = getattr(costume, "state_ids", [])
        for state_id in costume_state_ids:
            state = db.states.get(state_id)
            if state and getattr(state, "category", "") in scene_categories:
                applicable_states.append(state)

    if applicable_states:
        state_prompts = [s.prompt for s in applicable_states if s.prompt]
        state_neg_prompts = [
            s.negative_prompt for s in applicable_states if s.negative_prompt
        ]
        if state_prompts:
            final_prompt = ", ".join(filter(None, [final_prompt] + state_prompts))
        if state_neg_prompts:
            final_negative = ", ".join(
                filter(None, [final_negative] + state_neg_prompts)
            )

    return final_prompt, final_negative


def _combine_prompts(*prompts: Optional[str]) -> str:
    """None や空文字列を除外してカンマ区切りで結合"""
    return ", ".join(filter(None, [p.strip() if p else None for p in prompts]))


def _clean_prompt(text: str) -> str:
    """余分なカンマや括弧を整理"""
    text = re.sub(r"\(\s*,\s*\)", "", text)  # 空の括弧削除
    text = re.sub(r",\s*,", ",", text)  # 重複カンマ削除
    text = re.sub(r"^\s*,\s*", "", text)  # 先頭カンマ削除
    text = re.sub(r"\s*,\s*$", "", text)  # 末尾カンマ削除
    return text.strip()


# ==============================================================================
# Main Prompt Generation Logic
# ==============================================================================
def generate_batch_prompts(
    scene_id: str,
    actor_assignments: ActorAssignments,
    db: FullDatabase,
) -> List[GeneratedPrompt]:
    """
    シーンIDと配役情報から、衣装・ポーズ・表情の全組み合わせのプロンプトを生成。
    """
    scene = db.scenes.get(scene_id)
    if not scene:
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive=f"[Error: Scene {scene_id} not found]",
                negative="",
            )
        ]

    # --- 1. シーン共通パーツ取得 ---
    style = db.styles.get(scene.style_id) if scene.style_id else None
    background = db.backgrounds.get(scene.background_id)
    lighting = db.lighting.get(scene.lighting_id)
    composition = db.compositions.get(scene.composition_id)

    additional_prompts_list: List[AdditionalPrompt] = []
    if hasattr(scene, "additional_prompt_ids"):
        for ap_id in getattr(scene, "additional_prompt_ids", []):
            ap = db.additional_prompts.get(ap_id)
            if ap:
                additional_prompts_list.append(ap)

    # --- 2. Cut 取得 ---
    cut_obj = db.cuts.get(scene.cut_id) if scene.cut_id else None
    if not cut_obj:
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive=f"[Error: No valid cut for scene {scene.name}]",
                negative="",
            )
        ]

    # --- 3. 配役ごとの Appearance 組み合わせリストを作成 ---
    role_appearance_combinations: Dict[
        str, List[Dict[str, Optional[PromptPartBase]]]
    ] = {}
    valid_roles_in_scene: List[SceneRole] = []
    first_actor_info: Optional[Dict[str, Any]] = (
        None  # 最初の有効な配役情報 (ファイル名用)
    )

    scene_assignments_map = {ra.role_id: ra for ra in scene.role_assignments}

    for role in cut_obj.roles:
        actor_id = actor_assignments.get(role.id)
        actor = db.actors.get(actor_id) if actor_id else None
        if not actor:
            print(
                f"[WARN] No valid actor assigned for role {role.id} ({role.name_in_scene}) in scene {scene_id}. Skipping role."
            )
            continue  # この配役はプロンプト生成から除外

        valid_roles_in_scene.append(role)  # このロールは有効

        # 最初の有効なアクター情報を記録
        if not first_actor_info:
            character = (
                db.characters.get(actor.character_id) if actor.character_id else None
            )
            work = (
                db.works.get(character.work_id)
                if character and character.work_id
                else None
            )
            first_actor_info = {"actor": actor, "character": character, "work": work}

        role_assignment = scene_assignments_map.get(role.id)

        # 衣装・ポーズ・表情のIDリストを取得 (なければ Actor の基本設定)
        costume_ids = (
            role_assignment.costume_ids
            if role_assignment and role_assignment.costume_ids
            else [actor.base_costume_id]
        )
        pose_ids = (
            role_assignment.pose_ids
            if role_assignment and role_assignment.pose_ids
            else [actor.base_pose_id]
        )
        expression_ids = (
            role_assignment.expression_ids
            if role_assignment and role_assignment.expression_ids
            else [actor.base_expression_id]
        )

        # 各IDをオブジェクトに変換 (見つからない場合は None)
        costumes = [db.costumes.get(cid) for cid in costume_ids if cid]
        poses = [db.poses.get(pid) for pid in pose_ids if pid]
        expressions = [db.expressions.get(eid) for eid in expression_ids if eid]

        # リストが空になった場合 (ID が無効だった場合など) のフォールバック (None を追加)
        if not costumes:
            costumes.append(None)
        if not poses:
            poses.append(None)
        if not expressions:
            expressions.append(None)

        # この配役の Appearance 組み合わせ (デカルト積) を作成
        role_combinations = getCartesianProduct([costumes, poses, expressions])
        # 各組み合わせを Dict 形式に変換
        role_appearance_combinations[role.id] = [
            {"costume": combo[0], "pose": combo[1], "expression": combo[2]}
            for combo in role_combinations
        ]

    if not valid_roles_in_scene:
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive=f"[Error: No valid actors assigned in scene {scene.name}]",
                negative="",
            )
        ]

    # --- 4. 全配役の Appearance 組み合わせ (デカルト積) を計算 ---
    # 各配役の組み合わせリスト (role_appearance_combinations の値) を用意
    list_of_role_combination_lists = [
        role_appearance_combinations[role.id] for role in valid_roles_in_scene
    ]
    overall_combinations = getCartesianProduct(list_of_role_combination_lists)

    # --- 5. 全組み合わせをループしてプロンプト生成 ---
    generated_prompts: List[GeneratedPrompt] = []
    cut_base_name = cut_obj.name or f"Cut{scene.cut_id or 'N/A'}"
    global_prompt_index = 1

    for overall_combo in overall_combinations:
        # overall_combo は [role1_appearance_dict, role2_appearance_dict, ...] のリスト
        if len(overall_combo) != len(valid_roles_in_scene):
            print(f"[WARN] Skipping invalid combination: {overall_combo}")
            continue

        positive_prompts_per_role: Dict[str, str] = {}
        negative_prompts_per_role: Dict[str, str] = {}
        appearance_names_per_role: Dict[str, str] = {}  # プロンプト名用

        # 各配役のプロンプトを生成
        for i, role in enumerate(valid_roles_in_scene):
            role_id = role.id
            appearance: Dict[str, Optional[PromptPartBase]] = overall_combo[i]
            actor_id = actor_assignments[role_id]  # 必ず存在するはず
            actor = db.actors.get(actor_id)
            character = (
                db.characters.get(actor.character_id)
                if actor and actor.character_id
                else None
            )

            costume_obj = appearance.get("costume")
            pose_obj = appearance.get("pose")
            expression_obj = appearance.get("expression")

            # プロンプトパーツリスト (Actor は必須)
            parts: List[Optional[PromptPartBase]] = [
                actor,
                costume_obj,
                pose_obj,
                expression_obj,
            ]
            valid_parts = [p for p in parts if p is not None]

            # ポジティブ・ネガティブプロンプト結合 (State適用前)
            role_pos = _combine_prompts(
                *(getattr(p, "prompt", "") for p in valid_parts)
            )
            role_neg = _combine_prompts(
                *(getattr(p, "negative_prompt", "") for p in valid_parts)
            )

            # State 適用 (Costume があれば)
            role_pos, role_neg = _apply_state_prompts(
                role_pos, role_neg, costume_obj, scene, db
            )

            # カラーパレット適用
            role_pos = _apply_color_palette(role_pos, costume_obj, character)
            role_neg = _apply_color_palette(
                role_neg, costume_obj, character
            )  # ネガティブにも適用

            positive_prompts_per_role[role_id] = role_pos
            negative_prompts_per_role[role_id] = role_neg

            # プロンプト名用のパーツ名
            c_name = getattr(costume_obj, "name", actor.base_costume_id or "BaseC")
            p_name = getattr(pose_obj, "name", actor.base_pose_id or "BaseP")
            e_name = getattr(
                expression_obj, "name", actor.base_expression_id or "BaseE"
            )
            appearance_names_per_role[role_id] = f"{c_name}/{p_name}/{e_name}"

        # --- 6. テンプレートに代入 & 共通プロンプトと結合 ---
        final_positive = cut_obj.prompt_template
        final_negative = cut_obj.negative_template

        # プレイスホルダー ([R1], [R2] など) を置換
        for role_id, role_pos_prompt in positive_prompts_per_role.items():
            placeholder = f"[{role_id.upper()}]"
            # 括弧で囲む
            final_positive = final_positive.replace(placeholder, f"({role_pos_prompt})")

        for role_id, role_neg_prompt in negative_prompts_per_role.items():
            placeholder = f"[{role_id.upper()}]"
            final_negative = final_negative.replace(placeholder, f"({role_neg_prompt})")

        # 未解決の Role プレイスホルダーを削除
        final_positive = re.sub(r"\[R\d+\]", "", final_positive)
        final_negative = re.sub(r"\[R\d+\]", "", final_negative)

        # 共通プロンプト結合
        common_pos_parts = [
            getattr(style, "prompt", ""),
            final_positive,  # テンプレート置換後の文字列
            getattr(background, "prompt", ""),
            getattr(lighting, "prompt", ""),
            getattr(composition, "prompt", ""),
            *[ap.prompt for ap in additional_prompts_list if ap.prompt],
        ]
        common_neg_parts = [
            getattr(style, "negative_prompt", ""),
            final_negative,  # テンプレート置換後の文字列
            getattr(background, "negative_prompt", ""),
            getattr(lighting, "negative_prompt", ""),
            getattr(composition, "negative_prompt", ""),
            *[
                ap.negative_prompt
                for ap in additional_prompts_list
                if ap.negative_prompt
            ],
        ]

        final_positive = _clean_prompt(_combine_prompts(*common_pos_parts))
        final_negative = _clean_prompt(_combine_prompts(*common_neg_parts))

        # プロンプト名生成
        combo_name_parts = []
        for role in valid_roles_in_scene:
            actor = db.actors.get(actor_assignments[role.id])
            appearance_name = appearance_names_per_role.get(role.id, "N/A")
            combo_name_parts.append(
                f"{getattr(actor, 'name', role.id)}[{appearance_name}]"
            )
        combo_name = " & ".join(combo_name_parts)

        generated_prompts.append(
            GeneratedPrompt(
                cut=global_prompt_index,
                name=f"{cut_base_name}: {combo_name}",
                positive=final_positive,
                negative=final_negative,
                firstActorInfo=first_actor_info,
            )
        )
        global_prompt_index += 1

    return generated_prompts


def _sanitize_filename(name: Optional[str]) -> str:
    """ファイル名として安全な文字列に変換する"""
    if not name:
        return "unknown"
    # Windows/macOS/Linux で一般的に使えない文字を除去または置換
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # スペースもアンダースコアに置換 (オプション)
    name = name.replace(" ", "_")
    # 長すぎるファイル名を制限 (オプション)
    max_len = 100  # 例: 100文字
    if len(name) > max_len:
        name = name[:max_len]
    # 空文字になった場合のフォールバック
    return name if name else "unknown"


# --- ▼▼▼ create_image_generation_tasks を修正 ▼▼▼ ---
def create_image_generation_tasks(
    generated_prompts: List[GeneratedPrompt],
    cut: Optional[Cut],  # ★ Cut を受け取る
    scene: Optional[Scene],  # ★ Scene も受け取る
    db: FullDatabase,
) -> List[ImageGenerationTask]:
    if not cut or not scene:
        return []  # ★ Cut と Scene をチェック

    # SD Params は Scene から取得 (変更なし)
    sd_param_id = getattr(scene, "sd_param_id", None)
    sd_params = db.sdParams.get(sd_param_id) if sd_param_id else None
    if not sd_params:
        sd_params = next(
            iter(db.sdParams.values()),
            StableDiffusionParams(id="fallback", name="Fallback Default"),
        )
        print(
            f"[WARN] SD Params not found for scene '{getattr(scene, 'name', 'N/A')}'. Using fallback: {sd_params.name}"
        )

    safe_scene_name = _sanitize_filename(getattr(scene, "name", "unknown_scene"))
    tasks: List[ImageGenerationTask] = []

    for prompt_data in generated_prompts:
        # --- filename_prefix の生成ロジック (変更なし) ---
        work_title = "unknown_work"
        char_name = "unknown_character"
        if prompt_data.firstActorInfo:
            char = prompt_data.firstActorInfo.get("character")
            work = prompt_data.firstActorInfo.get("work")
            if char:
                char_name = getattr(char, "name", char_name)
            if work:
                work_title = getattr(work, "title_jp", work_title)

        safe_work = _sanitize_filename(work_title)
        safe_char = _sanitize_filename(char_name)
        # シーン名を含めることで、どのシーンのカットかわかりやすくする
        filename_prefix = (
            f"{safe_work}_{safe_char}_{safe_scene_name}_cut{prompt_data.cut}"
        )

        # --- ▼▼▼ mode, source_image_path を Cut から取得 ▼▼▼ ---
        mode = getattr(cut, "image_mode", "txt2img")
        source_image_path = getattr(cut, "reference_image_path", "")
        if not source_image_path or mode == "txt2img":
            mode = "txt2img"
            source_image_path = ""
        denoising_strength = sd_params.denoising_strength if mode != "txt2img" else None
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        task = ImageGenerationTask(
            prompt=prompt_data.positive,
            negative_prompt=prompt_data.negative,
            steps=sd_params.steps,
            sampler_name=sd_params.sampler_name,
            cfg_scale=sd_params.cfg_scale,
            seed=sd_params.seed,
            width=sd_params.width,
            height=sd_params.height,
            mode=mode,  # ★ Cut から取得した mode
            filename_prefix=filename_prefix,
            source_image_path=source_image_path,  # ★ Cut から取得した path
            denoising_strength=denoising_strength,
        )
        tasks.append(task)
    return tasks
