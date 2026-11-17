"""文本归一化工具。

归一化的目的：消除「看起来一样但不相等」的差异，包括
全角/半角差异、多余空白、中英文标点混用。
"""

from __future__ import annotations

import unicodedata

__all__ = ["normalize", "normalize_case_insensitive"]

# 中文标点 -> 英文标点。NFKC 只处理全角 ASCII 区字符，
# 中文标点（位于 U+3000 区段）需要显式映射。
_PUNCTUATION_MAP = str.maketrans({
    "。": ".",
    "、": ",",
    "，": ",",
    "；": ";",
    "：": ":",
    "？": "?",
    "！": "!",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "《": "<",
    "》": ">",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "—": "-",
    "～": "~",
    "·": ".",
})


def normalize(text: str | None) -> str:
    """归一化文本。

    处理顺序：NFKC 兼容归一化（全角转半角）-> 统一中英文标点 -> 去除全部空白。

    Args:
        text: 原始文本，允许为 None。

    Returns:
        归一化后的字符串；输入为 None 或空白时返回空串。

    Examples:
        >>> normalize(" ＡＢＣ 系统 ")
        'ABC系统'
        >>> normalize("论文（终稿）。")
        '论文(终稿).'
    """
    if not text:
        return ""
    result = unicodedata.normalize("NFKC", text)
    result = result.translate(_PUNCTUATION_MAP)
    return "".join(result.split())


def normalize_case_insensitive(text: str | None) -> str:
    """在 :func:`normalize` 基础上再忽略大小写。

    用于判断两个题目是否「仅大小写不同」。

    Args:
        text: 原始文本，允许为 None。

    Returns:
        归一化并转为小写后的字符串。

    Examples:
        >>> normalize_case_insensitive("ABC系统") == normalize_case_insensitive("abc系统")
        True
    """
    return normalize(text).casefold()
