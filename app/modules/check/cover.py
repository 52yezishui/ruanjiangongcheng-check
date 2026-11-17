"""从 PDF 封面（第 1 页）提取需要核对的字段。

范围界定（重要）：
    本模块**只做字段级文本提取**——论文题目、学院、学系、专业、姓名、
    学号、导师姓名共 7 个字段。
    它**不做**排版检查（字体、字号、行距、页边距），也**不读取论文正文**，
    符合 NFR08「不读取论文正文内容」的隐私约束。

依赖说明：
    使用 PyMuPDF（``fitz``）读取第 1 页文本。若环境中没有该库，或 PDF 加密
    无法读取，则所有字段返回 ``None``，由上层判定为「未识别，请人工确认」——
    这与真实系统的处理方式一致：不假装什么都能识别。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "COVER_FIELDS",
    "CoverExtraction",
    "extract_cover_fields",
    "HAS_FITZ",
]

try:  # pragma: no cover - 取决于运行环境
    import fitz  # type: ignore[import-untyped]

    HAS_FITZ = True
except Exception:  # noqa: BLE001 - 缺少可选依赖不应导致导入失败
    fitz = None  # type: ignore[assignment]
    HAS_FITZ = False

#: 需要核对的封面字段：键 -> 中文名。顺序即为界面展示顺序。
COVER_FIELDS: dict[str, str] = {
    "title": "论文题目",
    "college": "学院",
    "department": "学系",
    "major": "专业",
    "name": "姓名",
    "student_no": "学号",
    "supervisor_name": "导师姓名",
}

#: 标签别名表。同一字段在封面上可能有多种写法；
#: 长别名必须排在短别名之前（例如「导师姓名」先于「导师」）。
_LABEL_ALIASES: tuple[tuple[str, str], ...] = (
    ("论文题目", "title"),
    ("学位论文题目", "title"),
    ("题目", "title"),
    ("学院", "college"),
    ("学系", "department"),
    ("系别", "department"),
    ("专业", "major"),
    ("姓名", "name"),
    ("学号", "student_no"),
    ("导师姓名", "supervisor_name"),
    ("指导教师", "supervisor_name"),
    ("导师", "supervisor_name"),
)

# 封面标签常写成「学　院」「姓 名」，需要把中间空白去掉再匹配。
_BLANK = re.compile(r"[\s\u3000]+")
# 标签后可能出现冒号，需要剥离。
_TRIM_CHARS = ":： 　"


@dataclass(frozen=True)
class CoverExtraction:
    """封面提取结果。

    Attributes:
        fields: 字段键 -> 提取到的值；未识别为 None。
        page_text: 第 1 页的原始文本，便于排查提取失败的原因。
        available: 是否成功读取到 PDF 文本（库缺失或文件加密时为 False）。
        reason: 不可用的原因说明。
    """

    fields: dict[str, str | None] = field(default_factory=dict)
    page_text: str = ""
    available: bool = True
    reason: str = ""

    @property
    def recognized_count(self) -> int:
        """成功识别到的字段数量。"""
        return sum(1 for value in self.fields.values() if value)

    def missing(self) -> list[str]:
        """未识别到的字段中文名列表。"""
        return [COVER_FIELDS[key] for key, value in self.fields.items() if not value]


def _compact(text: str) -> str:
    """去掉全部空白，用于标签匹配。"""
    return _BLANK.sub("", text or "")


def _first_non_empty(lines: list[str], start: int) -> str:
    """从 start 起找第一行非空文本，且该行本身不是标签。"""
    for index in range(start, len(lines)):
        candidate = lines[index].strip(_TRIM_CHARS)
        if not candidate:
            continue
        if any(candidate.startswith(alias) for alias, _ in _LABEL_ALIASES):
            return ""
        return candidate
    return ""


def parse_cover_text(text: str) -> dict[str, str | None]:
    """从封面文本中解析字段。

    支持两种排版：标签与值在同一行（``学　院　网络空间安全学院``），
    或标签一行、值在下一行。

    Args:
        text: 第 1 页的纯文本。

    Returns:
        字段键 -> 值；未识别为 None。
    """
    result: dict[str, str | None] = {key: None for key in COVER_FIELDS}
    raw_lines = (text or "").splitlines()
    compact_lines = [_compact(line) for line in raw_lines]

    for index, compact in enumerate(compact_lines):
        if not compact:
            continue
        for alias, key in _LABEL_ALIASES:
            if result[key] is not None:
                continue
            if not compact.startswith(alias):
                continue
            value = compact[len(alias):].strip(_TRIM_CHARS)
            if not value:
                value = _first_non_empty(compact_lines, index + 1)
            if value:
                result[key] = value
            break

    return result


def extract_cover_fields(pdf_bytes: bytes) -> CoverExtraction:
    """从 PDF 字节流中提取封面字段。

    Args:
        pdf_bytes: PDF 文件内容。

    Returns:
        :class:`CoverExtraction`；无法读取时 ``available`` 为 False，
        且所有字段为 None。
    """
    empty = {key: None for key in COVER_FIELDS}

    if not HAS_FITZ:
        return CoverExtraction(empty, "", False, "未安装 PyMuPDF，无法提取封面字段")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 - 解析失败统一降级
        return CoverExtraction(empty, "", False, f"PDF 解析失败：{exc}")

    try:
        if document.is_encrypted:
            return CoverExtraction(empty, "", False, "PDF 已加密，封面无法读取")
        if document.page_count == 0:
            return CoverExtraction(empty, "", False, "PDF 没有页面")
        page_text = document.load_page(0).get_text()
    except Exception as exc:  # noqa: BLE001
        return CoverExtraction(empty, "", False, f"读取第 1 页失败：{exc}")
    finally:
        document.close()

    return CoverExtraction(parse_cover_text(page_text), page_text, True, "")
