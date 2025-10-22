# src/models.py
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# (Paste the dataclass definitions from the previous response here)
@dataclass
class PromptPartBase:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    prompt: str = ""
    negative_prompt: str = ""


# ... (Actor, Direction, Scene, etc.)


@dataclass
class StableDiffusionParams:
    steps: int = 20
    sampler_name: str = "Euler a"
    cfg_scale: float = 7.0
    # ... etc


@dataclass
class ImageGenerationTask:
    prompt: str
    # ... etc


# Helper to convert lists of dataclasses to JSON string for DB
def list_to_json_str(data_list: List) -> str:
    return json.dumps([item.__dict__ for item in data_list])


# Helper to convert JSON string back to list of dataclasses
def json_str_to_list(json_str: Optional[str], class_type) -> List:
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        return [class_type(**item) for item in data]
    except json.JSONDecodeError:
        print(f"Error decoding JSON for {class_type.__name__}: {json_str}")
        return []
