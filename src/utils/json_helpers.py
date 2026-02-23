# src/utils/json_helpers.py
import json
from typing import List, Optional, Dict, Any, Type, TypeVar
from dataclasses import is_dataclass, asdict

T = TypeVar("T")


def list_to_json_str(data_list: List[Any]) -> str:
    """リストをJSON文字列に変換します。dataclassオブジェクトも考慮します。"""
    if not data_list:
        return "[]"
    try:
        # dataclassオブジェクトなら辞書に変換、そうでなければそのまま使う
        return json.dumps(
            [asdict(item) if is_dataclass(item) else item for item in data_list],
            ensure_ascii=False,
        )
    except TypeError as e:
        print(f"Error encoding list to JSON: {e}. List: {data_list}")
        return "[]"


def json_str_to_list(json_str: Optional[str], class_type: Type[T]) -> List[T]:
    """JSON文字列を指定されたクラスのオブジェクトリストに変換します。"""
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        if not isinstance(data, list):
            print(
                f"Warning: Decoded JSON is not a list: {type(data)}. JSON: {json_str}"
            )
            return []

        items = []
        if callable(class_type) and is_dataclass(class_type):
            class_fields = {f.name for f in class_type.__dataclass_fields__.values()}
            for item_data in data:
                if isinstance(item_data, dict):
                    # dataclass のフィールドに存在しないキーをフィルタリング
                    filtered_data = {k: v for k, v in item_data.items() if k in class_fields}
                    try:
                        items.append(class_type(**filtered_data))
                    except TypeError as e:
                        print(f"Skipping item due to TypeError: {e}. Data: {filtered_data}")
                else:
                    # 辞書でない要素は無視
                    print(f"Skipping non-dict item in list: {item_data}")
            return items
        elif callable(class_type):
            return [class_type(item) for item in data]
        else:
            return data
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error decoding or creating instance for {getattr(class_type, '__name__', class_type)}: {e}")
        return []


def dict_to_json_str(data_dict: Dict[str, Any]) -> str:
    """辞書をJSON文字列に変換します。"""
    if not data_dict:
        return "{}"
    try:
        return json.dumps(data_dict, ensure_ascii=False)
    except TypeError as e:
        print(f"Error encoding dict to JSON: {e}. Dict: {data_dict}")
        return "{}"


def json_str_to_dict(json_str: Optional[str]) -> Dict[str, Any]:
    """JSON文字列を辞書に変換します。"""
    if not json_str:
        return {}
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            return data
        else:
            print(
                f"Warning: Decoded JSON is not a dict: {type(data)}. JSON: {json_str}"
            )
            return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON dict: {json_str}")
        return {}


# --- ★ データクラスリスト用ヘルパー ---
def dataclass_list_to_json_str(data_list: List[Any]) -> str:
    """データクラスのリストをJSON文字列に変換します。"""
    return list_to_json_str(data_list)  # list_to_json_str で対応可能


def json_str_to_dataclass_list(json_str: Optional[str], class_type: Type[T]) -> List[T]:
    """JSON文字列を指定されたデータクラスのリストに変換します。"""
    return json_str_to_list(json_str, class_type)  # json_str_to_list で対応可能
