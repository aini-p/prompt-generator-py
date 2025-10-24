# src/prompt_generator.py
import itertools
import re
from typing import Dict, List, Optional, Tuple, Mapping, TypeVar, Iterable
from .models import (
    FullDatabase,
    GeneratedPrompt,
    PromptPartBase,
    Actor,
    Scene,
    StableDiffusionParams,
    ImageGenerationTask,
    SceneRole,
    Work,
    Character,
    Scene,
    Costume,
    Style,
)

# UIから渡される「配役」
ActorAssignments = Mapping[
    str, str
]  # Read-only Map/Dict: Key: role.id, Value: actor.id

T = TypeVar("T")  # 型変数 T を定義


def getCartesianProduct(arrays: Iterable[Iterable[T]]) -> List[List[T]]:
    """
    ユーティリティ: 配列の直積（デカルト積）を計算する
    """
    pools = [
        list(pool) for pool in arrays if pool
    ]  # 入力をリストに変換し、空のiterableを除外
    if not pools:  # もし入力が空、または全て空のiterableなら
        return [[]]
    # itertools.product はイテレータを返すので list() でリストに変換
    # Note: product can return tuples, ensure downstream compatibility or convert tuples to lists here if needed
    # Converting to list of lists for consistency:
    return [list(item) for item in itertools.product(*pools)]


def generate_actor_prompt(
    actor: Actor, directionId: str, db: FullDatabase
) -> Dict[str, str]:
    """役者と演出から最終プロンプトを生成 (カラー置換含む)"""
    direction = db.directions.get(directionId)
    character: Optional[Character] = (
        db.characters.get(actor.character_id) if actor.character_id else None
    )

    # --- 使用するパーツを決定 ---
    costume: Optional[Costume] = None
    pose: Optional[PromptPartBase] = None
    expression: Optional[PromptPartBase] = None
    direction_part: Optional[Direction] = direction  # direction 自体もパーツとして扱う

    if not direction:  # 演出なし
        costume = db.costumes.get(actor.base_costume_id)
        pose = db.poses.get(actor.base_pose_id)
        expression = db.expressions.get(actor.base_expression_id)
    else:  # 演出あり
        costume_id = direction.costume_id or actor.base_costume_id
        costume = db.costumes.get(costume_id) if costume_id else None
        pose_id = direction.pose_id or actor.base_pose_id
        pose = db.poses.get(pose_id) if pose_id else None
        expression_id = direction.expression_id or actor.base_expression_id
        expression = db.expressions.get(expression_id) if expression_id else None

    # --- 有効なパーツリストを作成 ---
    finalParts: List[Optional[PromptPartBase]] = [
        actor,
        costume,
        pose,
        expression,
        direction_part,
    ]
    valid_final_parts = [p for p in finalParts if p is not None]

    # --- プロンプト文字列を結合 (置換前) ---
    positive_prompts_list: List[str] = []
    negative_prompts_list: List[str] = []
    for part in valid_final_parts:
        if part.prompt:
            positive_prompts_list.append(part.prompt)
        if part.negative_prompt:
            negative_prompts_list.append(part.negative_prompt)

    # --- ★ カラープレイスホルダー置換 ★ ---
    final_positive_str = ", ".join(positive_prompts_list)
    final_negative_str = ", ".join(negative_prompts_list)

    if costume and character and costume.color_palette:
        print(
            f"[DEBUG] Processing color palette for Costume: {costume.id} on Character: {character.id}"
        )
        replacements = {}  # 置換ペアを一時格納
        for item in costume.color_palette:
            placeholder = item.placeholder
            color_ref_str = item.color_ref
            attr_name = color_ref_str

            if hasattr(character, attr_name):
                color_value = getattr(character, attr_name, "")
                if color_value:  # カラー値が存在すれば置換リストに追加
                    print(
                        f"[DEBUG]   Found replacement: {placeholder} -> '{color_value}' (from {attr_name})"
                    )
                    replacements[placeholder] = color_value
                else:
                    print(
                        f"[DEBUG]   Skipping {placeholder}: Character attribute '{attr_name}' is empty."
                    )
            else:
                print(
                    f"[DEBUG]   Skipping {placeholder}: Character attribute '{attr_name}' not found."
                )

        # 実際に置換を実行 (プロンプト全体に対して)
        # Placeholderが他のPlaceholderの一部になっている場合を考慮し、長いものから置換 (例: [C10] と [C1])
        sorted_placeholders = sorted(replacements.keys(), key=len, reverse=True)
        for ph in sorted_placeholders:
            final_positive_str = final_positive_str.replace(ph, replacements[ph])
            final_negative_str = final_negative_str.replace(
                ph, replacements[ph]
            )  # ネガティブも置換

    # --- ★ 未解決のプレイスホルダーを削除 (オプション) ---
    # Costume で定義されたプレイスホルダー ([C1]など) が残っていたら削除
    if costume and costume.color_palette:
        remaining_placeholders = [item.placeholder for item in costume.color_palette]
        for ph in remaining_placeholders:
            # 正規表現のエスケープが必要な文字が含まれる可能性があるため re.escape を使う
            final_positive_str = final_positive_str.replace(ph, "")
            final_negative_str = final_negative_str.replace(ph, "")
    # カンマや空白の整理
    final_positive_str = ", ".join(
        filter(None, [s.strip() for s in final_positive_str.split(",")])
    )
    final_negative_str = ", ".join(
        filter(None, [s.strip() for s in final_negative_str.split(",")])
    )

    # --- 戻り値 ---
    actor_name_part = actor.name
    dir_name_part = f"({direction.name})" if direction else "(基本)"
    return {
        "name": f"{actor_name_part} {dir_name_part}",
        "positive": final_positive_str,
        "negative": final_negative_str,
    }


def generate_batch_prompts(
    scene_id: str,
    actor_assignments: ActorAssignments,
    db: FullDatabase,
    style_id: Optional[str] = None,
) -> List[GeneratedPrompt]:
    # --- ★ 修正: db["key"] -> db.attribute ---
    scene = db.scenes.get(scene_id)
    # --- ★ 修正ここまで ---
    if not scene:
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive=f"[Error: Scene {scene_id} not found]",
                negative="",
            )
        ]

    # --- ★ Style オブジェクトを取得 ---
    selected_style: Optional[Style] = db.styles.get(style_id) if style_id else None
    style_prompt = selected_style.prompt if selected_style else ""
    style_negative = selected_style.negative_prompt if selected_style else ""

    # --- 1. シーン共通パーツと共通プロンプト ---
    # --- ★ 修正: db["key"] -> db.attribute ---
    common_parts: List[Optional[PromptPartBase]] = [
        db.backgrounds.get(scene.background_id),
        db.lighting.get(scene.lighting_id),
        db.compositions.get(scene.composition_id),
    ]
    # --- ★ 修正ここまで ---
    valid_common_parts = [p for p in common_parts if p is not None]

    common_positive_base = ", ".join(
        filter(
            None,
            [style_prompt, scene.prompt_template]
            + [p.prompt for p in valid_common_parts],
        )
    )
    common_negative_base = ", ".join(
        filter(
            None,
            [style_negative, scene.negative_template]
            + [p.negative_prompt for p in valid_common_parts],
        )
    )

    # --- 2. 組み合わせ(直積)の準備 ---
    assigned_roles: List[SceneRole] = []
    direction_lists: List[List[str]] = []
    first_actor: Optional[Actor] = None
    first_character: Optional[Character] = None  # ★ 追加
    first_work: Optional[Work] = None  # ★ 追加

    for role in scene.roles:
        actor_id = actor_assignments.get(role.id)
        if actor_id:
            # --- ★ 修正: db["key"] -> db.attribute ---
            actor = db.actors.get(actor_id)
            # --- ★ 修正ここまで ---
            if actor:
                assigned_roles.append(role)
                if not first_actor:
                    first_actor = actor
                    # ★ Actor に紐づく Character と Work を取得
                    if actor.character_id:
                        first_character = db.characters.get(actor.character_id)
                        if first_character and first_character.work_id:
                            first_work = db.works.get(first_character.work_id)
                    # ★ 修正ここまで
                role_dir_obj = next(
                    (rd for rd in scene.role_directions if rd.role_id == role.id), None
                )
                directions = role_dir_obj.direction_ids if role_dir_obj else []
                direction_lists.append([""] if not directions else directions)

    if not assigned_roles:
        return [
            GeneratedPrompt(
                cut=1,
                name=f"Scene Base: {scene.name}",
                positive=common_positive_base.replace(r"\[[A-Z0-9]+\]", ""),
                negative=common_negative_base.replace(r"\[[A-Z0-9]+\]", ""),
            )
        ]

    # --- 3. 演出の組み合わせ（直積）を計算 ---
    all_combinations = getCartesianProduct(direction_lists)
    if not all_combinations or not isinstance(all_combinations, list):
        print("Error: getCartesianProduct did not return a valid list.")
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive="[Error calculating combinations]",
                negative="",
            )
        ]

    # --- 4. 組み合わせをループしてプロンプトを生成 ---
    generated_prompts: List[GeneratedPrompt] = []
    for i, combination in enumerate(all_combinations):
        final_positive = common_positive_base
        final_negative = common_negative_base
        cut_name_parts: List[str] = []

        if not isinstance(combination, list):
            continue

        for j, role in enumerate(assigned_roles):
            direction_id = combination[j] if j < len(combination) else ""
            actor_id = actor_assignments[role.id]
            # --- ★ 修正: db["key"] -> db.attribute ---
            actor = db.actors.get(actor_id)
            # --- ★ 修正ここまで ---
            if not actor:
                continue

            actor_prompt_parts = generate_actor_prompt(
                actor, direction_id, db
            )  # ★ db (FullDatabase) を渡す

            placeholder = f"[{role.id.upper()}]"
            final_positive = final_positive.replace(
                placeholder, f"({actor_prompt_parts['positive']})"
            )
            final_negative = final_negative.replace(
                placeholder, f"({actor_prompt_parts['negative']})"
            )
            cut_name_parts.append(actor_prompt_parts["name"])

        final_positive = final_positive.replace(r"\[[A-Z0-9]+\]", "")
        final_negative = final_negative.replace(r"\[[A-Z0-9]+\]", "")

        # --- ★ firstActorInfo に Character と Work オブジェクトを格納 ---
        first_actor_info_dict = None
        if first_character and first_work:  # Character と Work が取得できていれば
            first_actor_info_dict = {
                "character": first_character,
                "work": first_work,
            }
        # --- ★ 修正ここまで ---

        generated_prompts.append(
            GeneratedPrompt(
                cut=i + 1,
                name=" & ".join(cut_name_parts),
                positive=final_positive,
                negative=final_negative,
                firstActorInfo=first_actor_info_dict,  # 辞書または None を渡す
            )
        )

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


def create_image_generation_tasks(
    generated_prompts: List[GeneratedPrompt],
    sd_params: StableDiffusionParams,
    scene: Optional[Scene],
) -> List[ImageGenerationTask]:
    if not scene:
        return []

    safe_scene_name = _sanitize_filename(getattr(scene, "name", "unknown_scene"))

    tasks: List[ImageGenerationTask] = []
    for prompt_data in generated_prompts:
        # --- ▼▼▼ filename_prefix の生成ロジックを変更 ▼▼▼ ---
        work_title = "unknown_work"
        char_name = "unknown_character"
        actor_info = prompt_data.firstActorInfo
        if actor_info:
            char: Optional[Character] = actor_info.get("character")
            work: Optional[Work] = actor_info.get("work")
            if char:
                char_name = getattr(char, "name", "unknown_character")
            if work:
                work_title = getattr(
                    work, "title_jp", "unknown_work"
                )  # 日本語タイトルを使用

        # 安全なファイル名部分を生成
        safe_work = _sanitize_filename(work_title)
        safe_char = _sanitize_filename(char_name)

        # filename_prefix を組み立て
        filename_prefix = (
            f"{safe_work}_{safe_char}_{safe_scene_name}_cut{prompt_data.cut}"
        )

        mode = scene.image_mode
        source_image_path = scene.reference_image_path
        if not source_image_path:
            mode = "txt2img"
            source_image_path = ""
        denoising_strength = sd_params.denoising_strength if mode != "txt2img" else None

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
            filename_prefix=filename_prefix,
            source_image_path=source_image_path,
            denoising_strength=denoising_strength,
        )
        tasks.append(task)
    return tasks
