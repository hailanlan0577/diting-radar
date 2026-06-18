"""dig 镜头选题：从手写清单优先，兴趣兜底，去重已挖。"""
from __future__ import annotations
import os
import yaml
from diting.models import Interests


def _load_queue(queue_path: str) -> list[str]:
    """从 yaml 清单读话题列表。支持 list 或 {topics: [...]} dict 格式。"""
    if not queue_path or not os.path.exists(queue_path):
        return []
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return []
    if isinstance(data, dict):
        data = data.get("topics") or []
    if not isinstance(data, list):
        return []
    return [str(t).strip() for t in data if str(t).strip()]


def select_dig_topic(store, interests: Interests, queue_path: str) -> str | None:
    """选一个要深挖的话题。

    优先级：
    1. 从想挖清单（queue_path）取第一个未挖过的
    2. 清单空或不存在，从 interests.topics 取第一个未挖过的
    3. 都没有返回 None

    读 yaml 失败安全返 [] 而不抛异常。
    """
    for topic in _load_queue(queue_path):
        if not store.is_dug(topic):
            return topic
    for topic in interests.topics:
        if not store.is_dug(topic):
            return topic
    return None
