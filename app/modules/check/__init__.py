"""格式校验模块（CHK）。

对外接口（对应《系统概要设计》中的 validate）：

    >>> from app.modules.check import build_default_engine
    >>> engine = build_default_engine()
    >>> report = engine.check(submission)     # doctest: +SKIP

设计要点：
1. 规则通过参数注入，不直接依赖数据库，可脱离框架单独运行；
2. 规则采用抽象基类 + 子类的继承体系，引擎面向基类编程，新增规则不改引擎；
3. 全部数值阈值定义为模块级常量，无魔法数字；
4. PDF 封面字段提取（``cover``）与文件属性提取（``pdfmeta``）为可选增强，
   缺少 PyMuPDF 时自动降级为「未识别」，不影响核心校验逻辑。
"""

from __future__ import annotations

from .cover import COVER_FIELDS, CoverExtraction, extract_cover_fields
from .engine import CheckEngine, build_default_engine
from .models import CheckReport, CheckResult, RuleLevel
from .normalizer import normalize, normalize_case_insensitive
from .pdfmeta import PdfInfo, extract_file_info, looks_like_pdf
from .rules import (
    COVER_ITEMS,
    DEFAULT_MAX_SIZE_MB,
    DEFAULT_SCHOOL_CODE,
    EXTENSION,
    FILENAME_TEMPLATE,
    KIND_SUFFIX,
    CheckRule,
    CoverFieldRule,
    FileNameRule,
    FilePropertyRule,
)
from .similarity import classify, similarity

__all__ = [
    "CheckEngine",
    "build_default_engine",
    "CheckReport",
    "CheckResult",
    "RuleLevel",
    "normalize",
    "normalize_case_insensitive",
    "CheckRule",
    "CoverFieldRule",
    "FileNameRule",
    "FilePropertyRule",
    "classify",
    "similarity",
    "COVER_FIELDS",
    "COVER_ITEMS",
    "CoverExtraction",
    "extract_cover_fields",
    "PdfInfo",
    "extract_file_info",
    "looks_like_pdf",
    "DEFAULT_SCHOOL_CODE",
    "DEFAULT_MAX_SIZE_MB",
    "KIND_SUFFIX",
    "EXTENSION",
    "FILENAME_TEMPLATE",
]
