# src/prompt_generator.py
import itertools
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
    """
    役者(Actor)と単一の演出(Direction)から、
    その役者の最終的なプロンプトを生成する
    """
    direction = db.directions.get(directionId)
    if not direction:
        # 演出が見つからない(ID="")場合は、役者の基本状態のみ
        baseParts: List[Optional[PromptPartBase]] = [
            actor,
            db.costumes.get(actor.base_costume_id),
            db.poses.get(actor.base_pose_id),
            db.expressions.get(actor.base_expression_id),
        ]
        valid_base_parts = [p for p in baseParts if p is not None]  # Noneを除外

        return {
            "name": f"{actor.name} (基本)",
            "positive": ", ".join(filter(None, [p.prompt for p in valid_base_parts])),
            "negative": ", ".join(
                filter(None, [p.negative_prompt for p in valid_base_parts])
            ),
        }

    # 演出(Direction) に基づき、使用するパーツを「決定」
    finalParts: List[Optional[PromptPartBase]] = [
        actor,
        db.costumes.get(direction.costume_id)
        if direction.costume_id
        else db.costumes.get(actor.base_costume_id),
        db.poses.get(direction.pose_id)
        if direction.pose_id
        else db.poses.get(actor.base_pose_id),
        db.expressions.get(direction.expression_id)
        if direction.expression_id
        else db.expressions.get(actor.base_expression_id),
        direction,
    ]
    valid_final_parts = [p for p in finalParts if p is not None]  # Noneを除外

    return {
        "name": f"{actor.name} ({direction.name})",
        "positive": ", ".join(filter(None, [p.prompt for p in valid_final_parts])),
        "negative": ", ".join(
            filter(None, [p.negative_prompt for p in valid_final_parts])
        ),
    }


def generate_batch_prompts(
    scene_id: str,
    actor_assignments: ActorAssignments,
    db: FullDatabase,  # ★ 型ヒントを FullDatabase に
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
        filter(None, [scene.prompt_template] + [p.prompt for p in valid_common_parts])
    )
    common_negative_base = ", ".join(
        filter(
            None,
            [scene.negative_template] + [p.negative_prompt for p in valid_common_parts],
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


def create_image_generation_tasks(
    generated_prompts: List[GeneratedPrompt],
    sd_params: StableDiffusionParams,
    scene: Optional[Scene],
) -> List[ImageGenerationTask]:
    if not scene:
        return []
    tasks: List[ImageGenerationTask] = []
    for prompt_data in generated_prompts:
        filename_prefix = f"output_{prompt_data.cut}"
        actor_info = prompt_data.firstActorInfo
        # --- ★ firstActorInfo から Character, Work を取得 ---
        if actor_info:
            char: Optional[Character] = actor_info.get("character")
            work: Optional[Work] = actor_info.get("work")
            if char and work:
                # ファイル名に日本語タイトルとキャラ名を使う (ファイルシステムによっては注意)
                work_title = getattr(work, "title_jp", "unknown_work")
                char_name = getattr(char, "name", "unknown_char")
                # ファイル名に使えない文字を置換 (オプション)
                safe_work_title = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in work_title
                )
                safe_char_name = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in char_name
                )
                filename_prefix = (
                    f"{safe_work_title}_{safe_char_name}_cut{prompt_data.cut}"
                )
        # --- ★ 修正ここまで ---

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
