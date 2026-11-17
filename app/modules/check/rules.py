"""校验规则：抽象基类与三个具体规则类。

检查项清单（共 10 项）：

    ======  ==================  ==========================================
    编号     检查项              判定方式
    ======  ==================  ==========================================
    R01     文件名命名规范        整体一项判定（结构、学校代码、专业代码、
                                 学号归属、LW 后缀、.PDF 大小写），不拆项
    R02     文件格式             PDF 文件头魔数
    R03     文件大小             ≤ 30 MB 且大于 0
    R04     论文题目             精确比对 + 相似度分级
    R05     学院                三态比对
    R06     学系                三态比对
    R07     专业                三态比对
    R08     姓名                三态比对
    R09     学号                三态比对
    R10     导师姓名             三态比对
    ======  ==================  ==========================================

三态判定（封面字段）：

    已一致       提取值与学籍值归一化后相等
    不一致       两者都有值但不等            -> 错误（阻断）
    未识别       封面中提取不到该字段        -> 警告（转人工确认）

设计要点：
1. :class:`CheckRule` 为抽象基类，子类重写 :meth:`CheckRule.validate`；
2. 引擎面向基类编程，新增一类规则无需修改引擎（开闭原则）；
3. 所有阈值与上限均为模块级常量，代码中不出现魔法数字。
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .models import CheckResult, RuleLevel
from .normalizer import normalize, normalize_case_insensitive
from .similarity import (
    TITLE_MATCH_THRESHOLD,
    TITLE_WARN_THRESHOLD,
    similarity,
)

__all__ = [
    "CheckRule",
    "FileNameRule",
    "FilePropertyRule",
    "CoverFieldRule",
    "DEFAULT_SCHOOL_CODE",
    "KIND_SUFFIX",
    "EXTENSION",
    "DEFAULT_MAX_SIZE_MB",
    "FILENAME_TEMPLATE",
    "COVER_ITEMS",
]

#: 默认学校代码（暨南大学本科院校代码）。
DEFAULT_SCHOOL_CODE: str = "10559"
#: 命名规范要求的类型后缀（大写）。
KIND_SUFFIX: str = "LW"
#: 命名规范要求的扩展名（大写，不含点）。
EXTENSION: str = "PDF"
#: 单个文件大小上限（MB）。
DEFAULT_MAX_SIZE_MB: float = 30.0
#: 命名规范的人读模板，用于错误提示。
FILENAME_TEMPLATE: str = "学年_批次_学校代码_专业代码_学号_LW.PDF"

# 结构校验：学校代码固定 5 位、专业代码 6~7 位、学号 8~12 位。
# 大小写不在本正则中限制，由后续逐项目标比对给出结论。
_FILENAME_PATTERN = re.compile(
    r"^(?P<year_term>\d{4})_(?P<batch>\d{2})_(?P<school>\d{5})_"
    r"(?P<major_code>[0-9][0-9A-Za-z]{5,6})_(?P<student_no>\d{8,12})_"
    r"(?P<kind>[A-Za-z]{1,4})\.(?P<ext>[A-Za-z]+)$"
)

#: 封面字段与检查项编号的对应关系（顺序即展示顺序）。
COVER_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("R04", "title", "论文题目"),
    ("R05", "college", "学院"),
    ("R06", "department", "学系"),
    ("R07", "major", "专业"),
    ("R08", "name", "姓名"),
    ("R09", "student_no", "学号"),
    ("R10", "supervisor_name", "导师姓名"),
)


class CheckRule(ABC):
    """校验规则的抽象基类。

    子类只需实现 :meth:`validate`，并通过 :meth:`ok` / :meth:`fail`
    构造结果，保证输出格式统一。
    """

    def __init__(self, *, level: RuleLevel = RuleLevel.ERROR) -> None:
        """初始化规则。

        Args:
            level: 未通过时的默认级别，默认阻断（ERROR）。
        """
        self.level = level

    @abstractmethod
    def validate(self, submission: dict) -> list[CheckResult]:
        """执行校验。

        Args:
            submission: 提交信息字典，所需键见各子类 docstring。

        Returns:
            该规则产生的一条或多条检查结果。
        """

    def ok(self, code: str, item: str, message: str = "") -> CheckResult:
        """构造一条「通过」的结果。"""
        return CheckResult(code, item, passed=True, message=message)

    def fail(
        self,
        code: str,
        item: str,
        message: str,
        level: RuleLevel | None = None,
    ) -> CheckResult:
        """构造一条「未通过」的结果。

        Args:
            code: 检查项编号。
            item: 检查项名称。
            message: 面向用户的说明。
            level: 覆盖默认级别，用于产生警告而非错误。
        """
        return CheckResult(code, item, passed=False, level=level or self.level, message=message)


class FileNameRule(CheckRule):
    """R01：文件名命名规范（整体一项判定）。

    规范格式：``学年_批次_学校代码_专业代码_学号_LW.PDF``，
    例如 ``2526_44_10559_080904K_2022102893_LW.PDF``。

    本检查项一次性校验全部要求，**不拆分成多行、也不逐项诊断原因**：
    只要有一处不符即判不通过。

    校验内容：
        1. 六段结构与各段位数；
        2. 学校代码等于配置值；
        3. 学号段等于学籍库登记的学号（防止交错他人文件）；
        4. 类型后缀为 ``LW``；
        5. 扩展名为大写 ``.PDF``。

    submission 需要键：
        file_name (str): 上传的原始文件名。
        student (dict): 学籍信息，需含 student_no；
            若缺失则跳过「学号归属」一项，其余仍照常校验。
    """

    def __init__(
        self,
        *,
        school_code: str = DEFAULT_SCHOOL_CODE,
        kind_suffix: str = KIND_SUFFIX,
        extension: str = EXTENSION,
    ) -> None:
        """初始化规则。

        Args:
            school_code: 期望的学校代码。
            kind_suffix: 期望的类型后缀（大写）。
            extension: 期望的扩展名（大写，不含点）。
        """
        super().__init__()
        self.school_code = school_code
        self.kind_suffix = kind_suffix
        self.extension = extension

    def validate(self, submission: dict) -> list[CheckResult]:
        item = "文件名命名规范"
        file_name = str(submission.get("file_name") or "").strip()

        def reject() -> list[CheckResult]:
            return [
                self.fail(
                    "R01",
                    item,
                    f"文件名不符合命名规范，应为「{FILENAME_TEMPLATE}」，实际为「{file_name or '空'}」",
                )
            ]

        if not file_name:
            return reject()

        matched = _FILENAME_PATTERN.match(file_name)
        if matched is None:
            return reject()

        fields = matched.groupdict()

        if fields["school"] != self.school_code:
            return reject()
        if fields["kind"] != self.kind_suffix:
            return reject()
        if fields["ext"] != self.extension:
            return reject()

        expected_no = normalize((submission.get("student") or {}).get("student_no"))
        if expected_no and normalize(fields["student_no"]) != expected_no:
            return reject()

        return [self.ok("R01", item, file_name)]


class FilePropertyRule(CheckRule):
    """R02 ~ R03：文件属性校验。

    submission 需要键：
        is_pdf (bool | None): 文件内容是否为 PDF；None 表示未取得文件内容。
        size_mb (float | None): 文件大小，单位 MB。
    """

    def __init__(self, *, max_size_mb: float = DEFAULT_MAX_SIZE_MB) -> None:
        """初始化规则。

        Args:
            max_size_mb: 文件大小上限，单位 MB。
        """
        super().__init__()
        self.max_size_mb = max_size_mb

    def validate(self, submission: dict) -> list[CheckResult]:
        results: list[CheckResult] = []

        is_pdf = submission.get("is_pdf")
        if is_pdf is None:
            results.append(self.fail("R02", "文件格式", "未取得文件内容，无法判定格式"))
        elif is_pdf:
            results.append(self.ok("R02", "文件格式", "PDF"))
        else:
            results.append(
                self.fail("R02", "文件格式", "文件内容不是 PDF（缺少 %PDF- 文件头）")
            )

        size_mb = submission.get("size_mb")
        if size_mb is None:
            results.append(self.fail("R03", "文件大小", "未取得文件大小"))
        elif size_mb <= 0:
            results.append(self.fail("R03", "文件大小", f"文件大小异常：{size_mb:g} MB"))
        elif size_mb > self.max_size_mb:
            results.append(
                self.fail(
                    "R03",
                    "文件大小",
                    f"{size_mb:g} MB 超过上限 {self.max_size_mb:g} MB",
                )
            )
        else:
            results.append(self.ok("R03", "文件大小", f"{size_mb:g} MB"))

        return results


class CoverFieldRule(CheckRule):
    """R04 ~ R10：封面字段与学籍信息比对（三态判定）。

    submission 需要键：
        cover (dict): 封面提取到的字段，键为 title / college / department /
            major / name / student_no / supervisor_name；未识别为 None。
        student (dict): 学籍库登记值，键同上。

    论文题目采用「精确比对 + 相似度分级」，其余字段采用归一化后精确比对。
    """

    def __init__(
        self,
        *,
        match_threshold: float = TITLE_MATCH_THRESHOLD,
        warn_threshold: float = TITLE_WARN_THRESHOLD,
    ) -> None:
        """初始化规则。

        Args:
            match_threshold: 题目判定为一致的相似度下限。
            warn_threshold: 题目判定为疑似不一致的相似度下限。
        """
        super().__init__()
        self.match_threshold = match_threshold
        self.warn_threshold = warn_threshold

    def validate(self, submission: dict) -> list[CheckResult]:
        cover = submission.get("cover") or {}
        student = submission.get("student") or {}
        results: list[CheckResult] = []

        for code, key, label in COVER_ITEMS:
            extracted_raw = cover.get(key)
            expected_raw = student.get(key)
            extracted = normalize(extracted_raw)
            expected = normalize(expected_raw)

            if not extracted:
                results.append(
                    self.fail(code, label, "封面未识别到该项，请人工确认", level=RuleLevel.WARNING)
                )
                continue
            if not expected:
                results.append(
                    self.fail(code, label, "学籍库无该项记录，无法比对", level=RuleLevel.WARNING)
                )
                continue

            if key == "title":
                results.append(
                    self._judge_title(code, label, extracted_raw, expected_raw, extracted, expected)
                )
            else:
                results.append(
                    self._judge_exact(code, label, extracted_raw, expected_raw, extracted, expected)
                )

        return results

    def _judge_exact(
        self,
        code: str,
        label: str,
        extracted_raw: str | None,
        expected_raw: str | None,
        extracted: str,
        expected: str,
    ) -> CheckResult:
        """逐字符比对（已做归一化），仅大小写不同时单独提示。"""
        if extracted == expected:
            return self.ok(code, label)
        if extracted.casefold() == expected.casefold():
            return self.fail(
                code,
                label,
                f"仅大小写不一致：应为「{expected_raw}」，封面为「{extracted_raw}」",
            )
        return self.fail(code, label, f"应为「{expected_raw}」，封面为「{extracted_raw}」")

    def _judge_title(
        self,
        code: str,
        label: str,
        extracted_raw: str | None,
        expected_raw: str | None,
        extracted: str,
        expected: str,
    ) -> CheckResult:
        """题目比对：完全一致 -> 仅大小写不同 -> 相似度分级。"""
        if extracted == expected:
            return self.ok(code, label)

        score = similarity(extracted, expected)
        detail = f"相似度 {score:.3f}"

        if normalize_case_insensitive(extracted_raw) == normalize_case_insensitive(expected_raw):
            return self.fail(
                code,
                label,
                f"{detail}，仅大小写不同，请核对",
                level=RuleLevel.WARNING,
            )
        if score >= self.match_threshold:
            return self.ok(code, label, detail)
        if score >= self.warn_threshold:
            return self.fail(
                code,
                label,
                f"{detail}，与学籍登记题目疑似不一致，请人工确认",
                level=RuleLevel.WARNING,
            )
        return self.fail(code, label, f"{detail}，与学籍登记题目不一致")
