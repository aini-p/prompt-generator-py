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
        if callable(class_type) and is_dataclass(
            class_type
        ):  # データクラスの場合のみ**展開
            return [class_type(**item) for item in data if isinstance(item, dict)]
        elif callable(class_type):  # 通常のクラスや関数 (あまり使わない想定)
            return [class_type(item) for item in data]
        else:  # 型情報がない場合やプリミティブ型の場合
            print(
                f"Warning: class_type {class_type} is not callable or not dataclass for JSON list."
            )
            return data  # 変換せずにそのまま返す
    except json.JSONDecodeError:
        print(
            f"Error decoding JSON list for {getattr(class_type, '__name__', class_type)}: {json_str}"
        )
        return []
    except TypeError as e:
        print(
            f"Error creating instance of {getattr(class_type, '__name__', class_type)}: {e}. JSON part: {json_str[:100]}..."
        )
        # エラー時のフォールバック (オプション)
        valid_items = []
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and is_dataclass(class_type):
                        try:
                            valid_items.append(class_type(**item))
                        except TypeError:
                            pass
        except:
            pass
        return valid_items


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
