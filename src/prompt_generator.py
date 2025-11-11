# src/prompt_generator.py
import itertools
import re
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Mapping,
    TypeVar,
    Iterable,
    Any,
    TypeAlias,
)
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
    RoleAppearanceAssignment,
    Composition,
    BatchMetadata,
)

ActorAssignments = Mapping[str, str]  # Key: role.id, Value: actor.id
AppearanceOverrides: TypeAlias = Mapping[str, Mapping[str, Optional[str]]]
T = TypeVar("T")

# ==============================================================================
# Helper Functions (変更なし)
# ==============================================================================


def getCartesianProduct(arrays: Iterable[Iterable[T]]) -> List[List[T]]:
    """ユーティリティ: 配列の直積（デカルト積）を計算する"""
    pools = [list(pool) for pool in arrays if pool]
    if not pools:
        return [[]]
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
    text = re.sub(r"\(\s*,\s*\)", "", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"^\s*,\s*", "", text)
    text = re.sub(r"\s*,\s*$", "", text)
    return text.strip()


# ==============================================================================
# Main Prompt Generation Logic
# ==============================================================================
# --- ▼▼▼ generate_batch_prompts (component_name_str の生成ロジックを修正) ▼▼▼ ---
def generate_batch_prompts(
    scene_id: str,
    actor_assignments: ActorAssignments,
    appearance_overrides: AppearanceOverrides,
    db: FullDatabase,
) -> List[GeneratedPrompt]:
    """
    シーンIDと配役情報から、衣装・ポーズ・表情・構図の全組み合わせのプロンプトを生成。
    (SDParams はこの時点では考慮しない)
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

    style = db.styles.get(scene.style_id) if scene.style_id else None
    background = db.backgrounds.get(scene.background_id)
    lighting = db.lighting.get(scene.lighting_id)

    composition_list: List[Optional[Composition]] = []
    if hasattr(scene, "composition_ids") and scene.composition_ids:
        for comp_id in scene.composition_ids:
            comp = db.compositions.get(comp_id)
            if comp:
                composition_list.append(comp)
    if not composition_list:
        composition_list.append(None)

    additional_prompts_list: List[AdditionalPrompt] = []
    if hasattr(scene, "additional_prompt_ids"):
        for ap_id in getattr(scene, "additional_prompt_ids", []):
            ap = db.additional_prompts.get(ap_id)
            if ap:
                additional_prompts_list.append(ap)

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

    role_appearance_combinations: Dict[
        str, List[Dict[str, Optional[PromptPartBase]]]
    ] = {}
    valid_roles_in_scene: List[SceneRole] = []
    first_actor_info: Optional[Dict[str, Any]] = None

    scene_assignments_map = {ra.role_id: ra for ra in scene.role_assignments}

    for role in cut_obj.roles:
        actor_id = actor_assignments.get(role.id)
        actor = db.actors.get(actor_id) if actor_id else None
        if not actor:
            print(
                f"[WARN] No valid actor assigned for role {role.id} ({role.name_in_scene}) in scene {scene_id}. Skipping role."
            )
            continue

        valid_roles_in_scene.append(role)

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
        role_overrides = appearance_overrides.get(role.id, {})

        costume_override = role_overrides.get("costume_id")
        if costume_override:
            costume_ids = [costume_override]
        elif role_assignment and role_assignment.costume_ids:
            costume_ids = role_assignment.costume_ids
        else:
            costume_ids = [actor.base_costume_id]

        pose_override = role_overrides.get("pose_id")
        if pose_override:
            pose_ids = [pose_override]
        elif role_assignment and role_assignment.pose_ids:
            pose_ids = role_assignment.pose_ids
        else:
            pose_ids = [actor.base_pose_id]

        expression_override = role_overrides.get("expression_id")
        if expression_override:
            expression_ids = [expression_override]
        elif role_assignment and role_assignment.expression_ids:
            expression_ids = role_assignment.expression_ids
        else:
            expression_ids = [actor.base_expression_id]

        costumes = [db.costumes.get(cid) for cid in costume_ids if cid]
        poses = [db.poses.get(pid) for pid in pose_ids if pid]
        expressions = [db.expressions.get(eid) for eid in expression_ids if eid]

        if not costumes:
            costumes.append(None)
        if not poses:
            poses.append(None)
        if not expressions:
            expressions.append(None)

        role_combinations = getCartesianProduct([costumes, poses, expressions])
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

    list_of_role_combination_lists = [
        role_appearance_combinations[role.id] for role in valid_roles_in_scene
    ]
    overall_combinations = getCartesianProduct(list_of_role_combination_lists)

    generated_prompts: List[GeneratedPrompt] = []
    cut_base_name = cut_obj.name or f"Cut{scene.cut_id or 'N/A'}"
    global_prompt_index = 1

    all_combinations_product = itertools.product(overall_combinations, composition_list)

    for combo_product in all_combinations_product:
        overall_combo: List[Dict[str, Optional[PromptPartBase]]] = combo_product[0]
        composition: Optional[Composition] = combo_product[1]

        if len(overall_combo) != len(valid_roles_in_scene):
            print(f"[WARN] Skipping invalid combination: {overall_combo}")
            continue

        positive_prompts_per_role: Dict[str, str] = {}
        negative_prompts_per_role: Dict[str, str] = {}
        appearance_names_per_role: Dict[str, str] = {}

        for i, role in enumerate(valid_roles_in_scene):
            role_id = role.id
            appearance: Dict[str, Optional[PromptPartBase]] = overall_combo[i]
            actor_id = actor_assignments[role_id]
            actor = db.actors.get(actor_id)
            character = (
                db.characters.get(actor.character_id)
                if actor and actor.character_id
                else None
            )

            costume_obj = appearance.get("costume")
            pose_obj = appearance.get("pose")
            expression_obj = appearance.get("expression")

            parts: List[Optional[PromptPartBase]] = [
                actor,
                costume_obj,
                pose_obj,
                expression_obj,
            ]
            valid_parts = [p for p in parts if p is not None]

            role_pos = _combine_prompts(
                *(getattr(p, "prompt", "") for p in valid_parts)
            )
            role_neg = _combine_prompts(
                *(getattr(p, "negative_prompt", "") for p in valid_parts)
            )

            role_pos, role_neg = _apply_state_prompts(
                role_pos, role_neg, costume_obj, scene, db
            )
            role_pos = _apply_color_palette(role_pos, costume_obj, character)
            role_neg = _apply_color_palette(role_neg, costume_obj, character)

            positive_prompts_per_role[role_id] = role_pos
            negative_prompts_per_role[role_id] = role_neg

            c_name = getattr(costume_obj, "name", actor.base_costume_id or "BaseC")
            p_name = getattr(pose_obj, "name", actor.base_pose_id or "BaseP")
            e_name = getattr(
                expression_obj, "name", actor.base_expression_id or "BaseE"
            )
            appearance_names_per_role[role_id] = f"{c_name}/{p_name}/{e_name}"

        final_positive = cut_obj.prompt_template
        final_negative = cut_obj.negative_template

        for role_id, role_pos_prompt in positive_prompts_per_role.items():
            placeholder = f"[{role_id.upper()}]"
            final_positive = final_positive.replace(placeholder, f"({role_pos_prompt})")

        for role_id, role_neg_prompt in negative_prompts_per_role.items():
            placeholder = f"[{role_id.upper()}]"
            final_negative = final_negative.replace(placeholder, f"({role_neg_prompt})")

        final_positive = re.sub(r"\[R\d+\]", "", final_positive)
        final_negative = re.sub(r"\[R\d+\]", "", final_negative)

        common_pos_parts = [
            getattr(style, "prompt", ""),
            final_positive,
            getattr(background, "prompt", ""),
            getattr(lighting, "prompt", ""),
            getattr(composition, "prompt", ""),
            *[ap.prompt for ap in additional_prompts_list if ap.prompt],
        ]
        common_neg_parts = [
            getattr(style, "negative_prompt", ""),
            final_negative,
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

        # --- ▼▼▼ 修正箇所 ▼▼▼ ---

        # 1. UI表示用の名前 (従来通り、アクター名を含む)
        combo_name_parts_ui = []
        for role in valid_roles_in_scene:
            actor = db.actors.get(actor_assignments[role.id])
            appearance_name = appearance_names_per_role.get(role.id, "N/A")
            combo_name_parts_ui.append(
                f"{getattr(actor, 'name', role.id)}[{appearance_name}]"
            )
        comp_name = getattr(composition, "name", "BaseComp")
        combo_name_parts_ui.append(f"Comp[{comp_name}]")
        combo_name_ui = " & ".join(combo_name_parts_ui)

        # 2. ★ ファイル名用のコンポーネント文字列 (アクター名を使用)
        combo_name_parts_file = []
        for role in valid_roles_in_scene:
            appearance_name = appearance_names_per_role.get(role.id, "N/A")
            # ★ アクター名を取得して含める
            actor = db.actors.get(actor_assignments[role.id])
            actor_name = getattr(
                actor, "name", role.id
            )  # アクター名を取得、なければロールID
            combo_name_parts_file.append(
                f"{actor_name}[{appearance_name}]"  # ★ actor_name を使用
            )

        # ★ "BaseComp" はファイル名に含めない
        if comp_name != "BaseComp":
            combo_name_parts_file.append(comp_name)

        # ★ "_" で結合
        component_name_for_file = "_".join(combo_name_parts_file)

        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        generated_prompts.append(
            GeneratedPrompt(
                cut=global_prompt_index,
                name=f"{cut_base_name}: {combo_name_ui}",  # ★ UI表示用
                positive=final_positive,
                negative=final_negative,
                firstActorInfo=first_actor_info,
                composition=composition,
                component_name_str=component_name_for_file,  # ★ ファイル名用
            )
        )
        global_prompt_index += 1

    return generated_prompts


# --- ▲▲▲ generate_batch_prompts 修正ここまで ▲▲▲ ---


def _sanitize_filename(name: Optional[str]) -> str:
    """ファイル名として安全な文字列に変換する"""
    if not name:
        return "unknown"
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.replace(" ", "_")
    max_len = 100
    if len(name) > max_len:
        name = name[:max_len]
    return name if name else "unknown"


# --- ▼▼▼ create_image_generation_tasks (ファイル名生成部分を修正) ▼▼▼ ---
def create_image_generation_tasks(
    generated_prompts: List[GeneratedPrompt],
    cut: Optional[Cut],
    scene: Optional[Scene],
    db: FullDatabase,
) -> List[ImageGenerationTask]:
    """
    プロンプトリストとシーン設定に基づき、SD Param のデカルト積を含む
    最終的な ImageGenerationTask のリストを作成します。
    """
    if not cut or not scene:
        return []

    # --- 1. SD Params リストの取得 ---
    sd_params_list: List[StableDiffusionParams] = []
    if hasattr(scene, "sd_param_ids") and scene.sd_param_ids:
        for sdp_id in scene.sd_param_ids:
            sdp = db.sdParams.get(sdp_id)
            if sdp:
                sd_params_list.append(sdp)

    if not sd_params_list:
        default_sdp = next(
            iter(db.sdParams.values()),
            StableDiffusionParams(id="fallback", name="Fallback_Default"),
        )
        sd_params_list.append(default_sdp)
        print(
            f"[WARN] SD Params not found for scene '{getattr(scene, 'name', 'N/A')}'. Using fallback: {default_sdp.name}"
        )

    safe_scene_name = _sanitize_filename(getattr(scene, "name", "unknown_scene"))
    tasks: List[ImageGenerationTask] = []
    task_index = 1  # 最終的なタスクインデックス

    # --- 2. (プロンプト x SDParams) のデカルト積ループ ---
    for prompt_data in generated_prompts:
        for sd_params in sd_params_list:
            # --- ▼▼▼ 修正箇所 (作品名のみ取得) ▼▼▼ ---
            work_title = "unknown_work"
            if prompt_data.firstActorInfo:
                work = prompt_data.firstActorInfo.get("work")
                if work:
                    work_title = getattr(work, "title_jp", work_title)

            safe_work = _sanitize_filename(work_title)
            safe_sdp_name = _sanitize_filename(
                getattr(sd_params, "name", "default_sdp")
            )
            # --- ▲▲▲ 修正ここまで ▲▲▲ ---

            # 1. GeneratedPrompt から component_name_str を取得
            # (例: "ActorName[Costume/Pose/Expr]_CompName")
            base_comp_name = getattr(
                prompt_data, "component_name_str", f"p{prompt_data.cut}"
            )

            # 2. ファイル名用にクリーンアップ
            # "ActorName[Costume/Pose/Expr]_CompName" を
            # "ActorName-Costume_Pose_Expr_CompName" のように変換
            clean_comp_name = (
                base_comp_name.replace(
                    "/", "_"
                )  # Costume/Pose/Expr -> Costume_Pose_Expr
                .replace("[", "-")  # ActorName[ -> ActorName-
                .replace("]", "")  # ...Expr] -> ...Expr
                .replace(" ", "")  # スペース削除
            )

            # 3. 最終的なサニタイズ（Windowsの禁止文字などを処理）
            component_suffix = _sanitize_filename(clean_comp_name)

            # 4. filename_prefix を構築 (★ safe_char は含まない)
            filename_prefix = (
                f"{safe_work}_{safe_scene_name}_{component_suffix}_{safe_sdp_name}"
            )

            # --- ▲▲▲ 修正ここまで ▲▲▲ ---

            task_name = f"{prompt_data.name} | SDP[{safe_sdp_name}]"

            prompt_data.cut = task_index  # 最終タスクインデックスとして上書き
            task_index += 1

            mode = getattr(cut, "image_mode", "txt2img")
            source_image_path = getattr(cut, "reference_image_path", "")
            if not source_image_path or mode == "txt2img":
                mode = "txt2img"
                source_image_path = ""
            denoising_strength = (
                sd_params.denoising_strength if mode != "txt2img" else None
            )

            task = ImageGenerationTask(
                prompt=prompt_data.positive,
                negative_prompt=prompt_data.negative,
                steps=sd_params.steps,
                sampler_name=sd_params.sampler_name,
                cfg_scale=sd_params.cfg_scale,
                seed=sd_params.seed,
                width=sd_params.width,
                height=sd_params.height,
                mode=mode,
                filename_prefix=filename_prefix,  # ★ 修正された filename_prefix
                source_image_path=source_image_path,
                denoising_strength=denoising_strength,
                metadata=BatchMetadata(),
                # n_iter と batch_size は MainWindow 側で設定される
            )
            tasks.append(task)

    return tasks


# --- ▲▲▲ create_image_generation_tasks 修正ここまで ▲▲img2img_polish
