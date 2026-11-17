"""PDF / DOCX 文件属性提取。

只做「事实提取」——文件名、大小、扩展名、是否加密，
**不解析论文正文**，符合需求 NFR08「不读取论文正文内容」的隐私约束。

关于依赖：
    核心逻辑只用标准库；
    若环境中装有 PyMuPDF（``fitz``），则用它对加密状态做更准确的判断。
    这是「可选增强」，模块在没有 fitz 时同样可以工作。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = [
    "PdfInfo",
    "extract_file_info",
    "looks_like_pdf",
    "is_encrypted",
    "PDF_MAGIC",
    "HAS_FITZ",
]

#: PDF 文件头魔数。
PDF_MAGIC = b"%PDF-"
#: PDF 加密标记（位于 trailer 字典中）。
_ENCRYPT_MARKER = b"/Encrypt"
#: 判定加密时优先扫描的尾部窗口大小（字节）。
_TAIL_WINDOW = 8192

try:  # pragma: no cover - 取决于运行环境
    import fitz  # type: ignore[import-untyped]

    HAS_FITZ = True
except Exception:  # noqa: BLE001 - 缺少可选依赖不应导致导入失败
    fitz = None  # type: ignore[assignment]
    HAS_FITZ = False


@dataclass(frozen=True)
class PdfInfo:
    """从上传文件中提取到的属性。

    Attributes:
        file_name: 原始文件名（含扩展名）。
        extension: 小写扩展名，含点。
        size_bytes: 文件字节数。
        size_mb: 文件大小，单位 MB。
        encrypted: 是否为加密 PDF。非 PDF 一律为 False。
        detected_by: 加密状态的判定方式，用于在界面上说明数据来源。
    """

    file_name: str
    extension: str
    size_bytes: int
    size_mb: float
    encrypted: bool
    detected_by: str

    @property
    def is_pdf(self) -> bool:
        """是否为 PDF 文件。"""
        return self.extension == ".pdf"


def looks_like_pdf(data: bytes) -> bool:
    """按文件头魔数判断是否为 PDF。

    Args:
        data: 文件字节流。

    Returns:
        文件头为 ``%PDF-`` 时返回 True。

    Examples:
        >>> looks_like_pdf(b"%PDF-1.4 ...")
        True
        >>> looks_like_pdf(b"PK\\x03\\x04")
        False
    """
    return data[:5] == PDF_MAGIC


def is_encrypted(data: bytes) -> tuple[bool, str]:
    """判断 PDF 是否加密。

    优先使用 PyMuPDF 精确判定；若不可用或解析失败，退化为
    在文件尾部的 trailer 区扫描 ``/Encrypt`` 标记。

    Args:
        data: 文件字节流。

    Returns:
        ``(是否加密, 判定方式)`` 二元组。
    """
    if not looks_like_pdf(data):
        return False, "非 PDF，无需判定"

    if HAS_FITZ:
        try:
            with fitz.open(stream=data, filetype="pdf") as document:  # type: ignore[union-attr]
                return bool(document.is_encrypted), "PyMuPDF"
        except Exception:  # noqa: BLE001 - 解析失败时退化到关键字扫描
            pass

    if _ENCRYPT_MARKER in data[-_TAIL_WINDOW:]:
        return True, "关键字扫描（尾部 trailer）"
    if _ENCRYPT_MARKER in data:
        return True, "关键字扫描（全文）"
    return False, "关键字扫描"


def extract_file_info(file_name: str, data: bytes) -> PdfInfo:
    """从文件名与字节流中提取属性。

    Args:
        file_name: 上传时的原始文件名。
        data: 文件内容。

    Returns:
        提取到的 :class:`PdfInfo`。

    Examples:
        >>> info = extract_file_info("10559_2026123456_昝博_网络空间安全.pdf", b"%PDF-1.4")
        >>> info.extension, info.encrypted
        ('.pdf', False)
    """
    extension = os.path.splitext(file_name or "")[1].lower()
    size_bytes = len(data or b"")
    size_mb = size_bytes / (1024 * 1024)
    encrypted, detected_by = is_encrypted(data or b"")
    return PdfInfo(
        file_name=file_name or "",
        extension=extension,
        size_bytes=size_bytes,
        size_mb=size_mb,
        encrypted=encrypted,
        detected_by=detected_by,
    )
