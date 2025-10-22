# src/prompt_generator.py
import itertools
from typing import Dict, List, Optional, Tuple, Mapping # Use Mapping for read-only dict hint
from .models import (
    FullDatabase, GeneratedPrompt, PromptPartBase, Actor, Scene,
    StableDiffusionParams, ImageGenerationTask, SceneRole
)

# Define ActorAssignments type hint
ActorAssignments = Mapping[str, str] # Read-only Map/Dict: Key: role.id, Value: actor.id

# (Copy the getCartesianProduct and generate_actor_prompt functions from v10 response here)
def getCartesianProduct<T>(arrays: T[][]): T[][] { /* ... */ }
def generate_actor_prompt(actor: Actor, directionId: str, db: FullDatabase): { name: string, positive: string, negative: string } { /* ... */ }


def generate_batch_prompts(
    scene_id: str,
    actor_assignments: ActorAssignments, # Use Mapping hint
    db: FullDatabase # Pass the whole DB dictionary
) -> List[GeneratedPrompt]:

    scene = db['scenes'].get(scene_id)
    if not scene:
        return [{"cut": 0, "name": "Error", "positive": f"[Error: Scene {scene_id} not found]", "negative": ""}]

    # --- 1. Common parts and prompts ---
    common_parts: List[PromptPartBase] = [
        db['backgrounds'].get(scene.background_id),
        db['lighting'].get(scene.lighting_id),
        db['compositions'].get(scene.composition_id),
    ]
    common_parts = [p for p in common_parts if p] # Filter out None

    common_positive_base = ', '.join(filter(None, [scene.prompt_template] + [p.prompt for p in common_parts]))
    common_negative_base = ', '.join(filter(None, [scene.negative_template] + [p.negative_prompt for p in common_parts]))

    # --- 2. Prepare combinations ---
    assigned_roles: List[SceneRole] = []
    direction_lists: List[List[str]] = []
    first_actor: Optional[Actor] = None

    for role in scene.roles:
        actor_id = actor_assignments.get(role.id)
        if actor_id:
            actor = db['actors'].get(actor_id)
            if actor:
                assigned_roles.append(role)
                if not first_actor:
                    first_actor = actor

                role_dir_obj = next((rd for rd in scene.role_directions if rd.role_id == role.id), None)
                directions = role_dir_obj.direction_ids if role_dir_obj else []
                direction_lists.append([""] if not directions else directions) # Use [""] for base state

    if not assigned_roles:
        # No actors assigned, return only scene base prompts
        return [{"cut": 1, "name": f"Scene Base: {scene.name}",
                 "positive": common_positive_base.replace(r'\[[A-Z0-9]+\]', ''),
                 "negative": common_negative_base.replace(r'\[[A-Z0-9]+\]', '')}]

    # --- 3. Calculate Cartesian product ---
    all_combinations = list(itertools.product(*direction_lists))

    # --- 4. Generate prompts for each combination ---
    generated_prompts: List[GeneratedPrompt] = []
    for i, combination in enumerate(all_combinations):
        final_positive = common_positive_base
        final_negative = common_negative_base
        cut_name_parts: List[str] = []

        for j, role in enumerate(assigned_roles):
            direction_id = combination[j]
            actor_id = actor_assignments[role.id] # We know it exists from step 2
            actor = db['actors'].get(actor_id)
            if not actor: continue # Should not happen if DB is consistent

            actor_prompt_parts = generate_actor_prompt(actor, direction_id, db)

            placeholder = f"[{role.id.upper()}]"
            # Replace placeholder using f-string or simple replace
            final_positive = final_positive.replace(placeholder, f"({actor_prompt_parts['positive']})")
            final_negative = final_negative.replace(placeholder, f"({actor_prompt_parts['negative']})")
            cut_name_parts.append(actor_prompt_parts['name'])

        # Remove any remaining placeholders
        final_positive = final_positive.replace(r'\[[A-Z0-9]+\]', '')
        final_negative = final_negative.replace(r'\[[A-Z0-9]+\]', '')

        first_actor_info = None
        if first_actor:
             first_actor_info = {"work_title": first_actor.work_title, "character_name": first_actor.character_name}

        generated_prompts.append({ # Use dict literal matching GeneratedPrompt structure
            "cut": i + 1,
            "name": ' & '.join(cut_name_parts),
            "positive": final_positive,
            "negative": final_negative,
            "firstActorInfo": first_actor_info # Pass dict or None
        })

    return generated_prompts

def create_image_generation_tasks(
    generated_prompts: List[GeneratedPrompt],
    sd_params: StableDiffusionParams,
    scene: Optional[Scene]
) -> List[ImageGenerationTask]:
    if not scene: return []

    tasks: List[ImageGenerationTask] = []
    for prompt_data in generated_prompts:
        filename_prefix = f"output_{prompt_data['cut']}" # Use dict access
        actor_info = prompt_data.get('firstActorInfo')
        if actor_info:
            filename_prefix = f"{actor_info['work_title']}_{actor_info['character_name']}_cut{prompt_data['cut']}"

        mode = scene.image_mode
        source_image_path = scene.reference_image_path
        if not source_image_path:
            mode = "txt2img"
            source_image_path = ""

        denoising_strength = sd_params.denoising_strength if mode != "txt2img" else None # Use None for non-img2img

        task = ImageGenerationTask(
            prompt=prompt_data['positive'],
            negative_prompt=prompt_data['negative'],
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