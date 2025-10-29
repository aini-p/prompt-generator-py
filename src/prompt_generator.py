# src/prompt_generator.py
import itertools
import re
from typing import Dict, List, Optional, Tuple, Mapping, TypeVar, Iterable
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
    Style,
    State,
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
    actor: Actor,
    directionId: str,
    scene: Scene,  # ★ Scene 引数を追加
    db: FullDatabase,
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

    # --- ▼▼▼ Costume プロンプトに State プロンプトを追記 ▼▼▼ ---
    costume_prompt = ""
    costume_negative_prompt = ""
    if costume:
        costume_prompt = costume.prompt
        costume_negative_prompt = costume.negative_prompt

        # Scene の state_categories と Costume の state_ids から適用する State を探す
        applicable_states: List[State] = []
        scene_categories = set(getattr(scene, "state_categories", []))
        if scene_categories and hasattr(costume, "state_ids"):
            costume_state_ids = getattr(costume, "state_ids", [])
            for state_id in costume_state_ids:
                state = db.states.get(state_id)
                if state and getattr(state, "category", "") in scene_categories:
                    applicable_states.append(state)

        # 適用する State のプロンプトを追記
        if applicable_states:
            # カテゴリなどでソートする？ここでは単純に結合
            state_prompts = [s.prompt for s in applicable_states if s.prompt]
            state_neg_prompts = [
                s.negative_prompt for s in applicable_states if s.negative_prompt
            ]

            if state_prompts:
                costume_prompt += ", " + ", ".join(state_prompts)
            if state_neg_prompts:
                costume_negative_prompt += ", " + ", ".join(state_neg_prompts)
    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    # --- 有効なパーツリストを作成 ---
    # ★ Costume の代わりに、State適用済みのプロンプトを持つ一時オブジェクトを使うか、
    #    あるいは costume 変数自体を使わないようにする。
    #    ここでは Costume のプロンプトを使わず、上で加工した文字列を使う。
    finalParts: List[Optional[PromptPartBase]] = [
        actor,  # actor.prompt, actor.negative_prompt
        # costume, # costume.prompt, costume.negative_prompt は使わない
        pose,
        expression,
        direction_part,
    ]
    valid_final_parts = [p for p in finalParts if p is not None]

    # --- プロンプト文字列を結合 (置換前) ---
    positive_prompts_list: List[str] = [
        costume_prompt
    ]  # ★ State適用済み Costume プロンプトから開始
    negative_prompts_list: List[str] = [costume_negative_prompt]  # ★
    for part in valid_final_parts:
        if part.prompt:
            positive_prompts_list.append(part.prompt)
        if part.negative_prompt:
            negative_prompts_list.append(part.negative_prompt)

    # --- ★ カラープレイスホルダー置換 ★ ---
    final_positive_str = ", ".join(
        filter(None, positive_prompts_list)
    )  # filter(None, ...) を追加
    final_negative_str = ", ".join(
        filter(None, negative_prompts_list)
    )  # filter(None, ...) を追加
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


# --- ▼▼▼ generate_batch_prompts を修正 ▼▼▼ ---
def generate_batch_prompts(
    scene_id: str,
    actor_assignments: ActorAssignments,
    db: FullDatabase,
    # style_id: Optional[str] = None, # ← 削除
) -> List[GeneratedPrompt]:
    scene = db.scenes.get(scene_id)
    if not scene:
        # ... (エラー処理は変更なし) ...
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive=f"[Error: Scene {scene_id} not found]",
                negative="",
            )
        ]

    # ▼▼▼ Style を Scene から取得 ▼▼▼
    style_id = getattr(scene, "style_id", None)
    selected_style: Optional[Style] = db.styles.get(style_id) if style_id else None
    style_prompt = selected_style.prompt if selected_style else ""
    style_negative = selected_style.negative_prompt if selected_style else ""
    # ▲▲▲ 修正ここまで ▲▲▲

    # --- 1. シーン共通パーツ (変更なし) ---
    common_parts: List[Optional[PromptPartBase]] = [
        db.backgrounds.get(scene.background_id),
        db.lighting.get(scene.lighting_id),
        db.compositions.get(scene.composition_id),
    ]
    valid_common_parts = [p for p in common_parts if p is not None]

    # --- ▼▼▼ Cut ごとのプロンプト生成ループ (変更なし) ▼▼▼ ---
    generated_prompts_all_cuts: List[GeneratedPrompt] = []
    global_cut_index = 1  # 全カットを通したインデックス

    # Scene が持つ cut_id から Cut オブジェクトを取得
    target_cut_id = scene.cut_id
    cut_obj: Optional[Cut] = db.cuts.get(target_cut_id) if target_cut_id else None

    if not cut_obj:
        print(
            f"[WARN] Scene {scene_id} has no valid Cut selected (cut_id: {target_cut_id})."
        )
        return [
            GeneratedPrompt(
                cut=0,
                name="Error",
                positive=f"[Error: No valid cut selected for scene {getattr(scene, 'name', 'N/A')}]",
                negative="",
            )
        ]

    cut_name_prefix = cut_obj.name or f"Cut{global_cut_index}"

    # --- 2. Cut の台本と共通パーツプロンプトを結合 (Style 取得部分以外変更なし) ---
    common_positive_base = ", ".join(
        filter(
            None,
            [
                style_prompt,  # Scene から取得した Style を使用
                cut_obj.prompt_template,
                *[p.prompt for p in valid_common_parts],
            ],
        )
    )
    common_negative_base = ", ".join(
        filter(
            None,
            [
                style_negative,  # Scene から取得した Style を使用
                cut_obj.negative_template,
                *[p.negative_prompt for p in valid_common_parts],
            ],
        )
    )

    # --- 3. 組み合わせ(直積)の準備 (変更なし) ---
    assigned_roles: List[SceneRole] = []
    direction_lists: List[List[str]] = []
    first_actor: Optional[Actor] = None
    first_character: Optional[Character] = None
    first_work: Optional[Work] = None

    for role in cut_obj.roles:
        actor_id = actor_assignments.get(role.id)
        if actor_id:
            actor = db.actors.get(actor_id)
            if actor:
                assigned_roles.append(role)
                if not first_actor:
                    first_actor = actor
                    if actor.character_id:
                        first_character = db.characters.get(actor.character_id)
                        if first_character and first_character.work_id:
                            first_work = db.works.get(first_character.work_id)
                role_dir_obj = next(
                    (rd for rd in scene.role_directions if rd.role_id == role.id), None
                )
                directions = role_dir_obj.direction_ids if role_dir_obj else []
                # 演出が空でも、組み合わせのために空文字列のリストを追加
                direction_lists.append([""] if not directions else directions)
            else:
                print(f"[WARN] Actor {actor_id} assigned to role {role.id} not found.")
                # アクターが見つからない場合、このロールはスキップするかエラーにするか
                # ここではスキップし、direction_lists にも追加しない
        else:
            print(
                f"[WARN] No actor assigned to role {role.id} ({role.name_in_scene}) in cut {cut_obj.id}."
            )
            # アサインされていないロールもスキップ

    # --- 4. 組み合わせ生成の前にチェック ---
    if not assigned_roles:
        # 配役が一人もいない、または有効なアクターが割り当てられていない場合
        generated_prompts_all_cuts.append(
            GeneratedPrompt(
                cut=global_cut_index,
                name=f"{cut_name_prefix}: Base (No Actors)",
                positive=re.sub(r"\[R\d+\]", "", common_positive_base).strip(", "),
                negative=re.sub(r"\[R\d+\]", "", common_negative_base).strip(", "),
                firstActorInfo=None,
            )
        )
        global_cut_index += 1
        return generated_prompts_all_cuts  # このカットの処理は終了

    # --- 5. 演出の組み合わせ（直積）を計算 (変更なし) ---
    all_combinations = getCartesianProduct(direction_lists)
    if not all_combinations or not isinstance(all_combinations, list):
        print(f"Error: getCartesianProduct failed for cut {cut_obj.id}.")
        return generated_prompts_all_cuts  # エラー発生時はこれまでのプロンプトを返す

    # --- 6. 組み合わせをループしてプロンプトを生成 (変更なし) ---
    for i, combination in enumerate(all_combinations):
        final_positive = common_positive_base
        final_negative = common_negative_base
        cut_variation_name_parts: List[str] = []

        if not isinstance(combination, list) or len(combination) != len(
            assigned_roles  # direction_lists と assigned_roles の要素数は一致するはず
        ):
            print(
                f"Warning: Invalid combination skipped for cut {cut_obj.id}: {combination}"
            )
            continue

        for j, role in enumerate(assigned_roles):
            direction_id = combination[
                j
            ]  # combination は ["dir_id1", "", "dir_id3", ...]
            actor_id = actor_assignments[role.id]
            actor = db.actors.get(actor_id)
            if not actor:
                continue  # アクターが見つからない場合はスキップ

            actor_prompt_parts = generate_actor_prompt(actor, direction_id, scene, db)

            placeholder = f"[{role.id.upper()}]"
            # 括弧で囲むことで強度を上げる (LoRA などで役立つ場合がある)
            final_positive = final_positive.replace(
                placeholder, f"({actor_prompt_parts['positive']})"
            )
            final_negative = final_negative.replace(
                placeholder, f"({actor_prompt_parts['negative']})"
            )
            cut_variation_name_parts.append(actor_prompt_parts["name"])

        # 未解決のシーン Role プレイスホルダー ([R3] など) を削除
        final_positive = re.sub(r"\[R\d+\]", "", final_positive)
        final_negative = re.sub(r"\[R\d+\]", "", final_negative)
        # 空の括弧 () や余分なカンマを整理
        final_positive = re.sub(r"\(\s*,\s*\)", "", final_positive)
        final_positive = re.sub(r",\s*,", ",", final_positive).strip(", ")
        final_negative = re.sub(r"\(\s*,\s*\)", "", final_negative)
        final_negative = re.sub(r",\s*,", ",", final_negative).strip(", ")

        first_actor_info_dict = None
        if first_character and first_work:
            first_actor_info_dict = {
                "character": first_character,
                "work": first_work,
            }

        generated_prompts_all_cuts.append(
            GeneratedPrompt(
                cut=global_cut_index,  # ★ グローバルインデックスを使用
                name=f"{cut_name_prefix}: {' & '.join(cut_variation_name_parts)}",
                positive=final_positive,
                negative=final_negative,
                firstActorInfo=first_actor_info_dict,
            )
        )
        global_cut_index += 1  # グローバルインデックスをインクリメント

    return generated_prompts_all_cuts  # 全カットの結果を返す


# --- ▲▲▲ 修正ここまで ▲▲▲ ---


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
