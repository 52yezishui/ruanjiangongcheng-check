"""字符串相似度计算与分级判定。

阈值集中定义为模块级常量，避免在代码中出现魔法数字。
"""

from __future__ import annotations

from difflib import SequenceMatcher

__all__ = [
    "TITLE_MATCH_THRESHOLD",
    "TITLE_WARN_THRESHOLD",
    "MATCHED",
    "SUSPECTED",
    "MISMATCHED",
    "similarity",
    "classify",
]

#: 判定为「一致」的相似度下限。
TITLE_MATCH_THRESHOLD: float = 0.98
#: 判定为「疑似不一致」的相似度下限；低于此值判为「不一致」。
TITLE_WARN_THRESHOLD: float = 0.80

MATCHED = "一致"
SUSPECTED = "疑似不一致"
MISMATCHED = "不一致"


def similarity(left: str, right: str) -> float:
    """计算两个字符串的相似度。

    Args:
        left: 字符串一。
        right: 字符串二。

    Returns:
        0.0 到 1.0 之间的相似度。两者完全相同返回 1.0；
        任一为空返回 0.0（空串与任何文本都不算一致）。

    Examples:
        >>> similarity("abc", "abc")
        1.0
        >>> similarity("", "abc")
        0.0
    """
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def classify(score: float) -> str:
    """按相似度给出判定结论。

    Args:
        score: 相似度，取值范围 0.0 到 1.0。

    Returns:
        三档判定之一：``一致``（>= 0.98）、``疑似不一致``（0.80 ~ 0.98）、
        ``不一致``（< 0.80）。

    Examples:
        >>> classify(0.99), classify(0.85), classify(0.50)
        ('一致', '疑似不一致', '不一致')
    """
    if score >= TITLE_MATCH_THRESHOLD:
        return MATCHED
    if score >= TITLE_WARN_THRESHOLD:
        return SUSPECTED
    return MISMATCHED
