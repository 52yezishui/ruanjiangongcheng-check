"""格式校验模块的数据模型。

本模块只使用 Python 标准库，可脱离 Web 框架与数据库独立运行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = ["RuleLevel", "CheckResult", "CheckReport"]


class RuleLevel(str, Enum):
    """规则严重级别。

    ERROR 会阻断流程；WARNING 不阻断，但标记为待人工确认。
    """

    ERROR = "错误"
    WARNING = "警告"


@dataclass(frozen=True)
class CheckResult:
    """单条检查项的结果。

    Attributes:
        rule_code: 检查项编号，如 R01。
        item: 检查项名称，如「学校代码」。
        passed: 是否通过。
        level: 严重级别，仅在未通过时有意义。
        message: 面向用户的说明，要求无歧义、可指导修改。
    """

    rule_code: str
    item: str
    passed: bool
    level: RuleLevel = RuleLevel.ERROR
    message: str = ""

    @property
    def status_text(self) -> str:
        """用于界面展示的状态文字。"""
        if self.passed:
            return "通过"
        return self.level.value

    def to_line(self) -> str:
        """渲染成一行可读文本，用于终端输出。"""
        text = f"[{self.status_text}] {self.rule_code} {self.item}"
        if not self.passed and self.message:
            text = f"{text}：{self.message}"
        return text


@dataclass
class CheckReport:
    """一次完整校验的报告，由多条 CheckResult 聚合而成。"""

    submission_id: str | None = None
    results: list[CheckResult] = field(default_factory=list)

    def add(self, results: CheckResult | list[CheckResult]) -> None:
        """追加一条或多条结果。"""
        if isinstance(results, CheckResult):
            self.results.append(results)
        else:
            self.results.extend(results)

    @property
    def errors(self) -> list[CheckResult]:
        """所有未通过且级别为「错误」的结果。"""
        return [r for r in self.results if not r.passed and r.level is RuleLevel.ERROR]

    @property
    def warnings(self) -> list[CheckResult]:
        """所有未通过且级别为「警告」的结果。"""
        return [r for r in self.results if not r.passed and r.level is RuleLevel.WARNING]

    @property
    def has_error(self) -> bool:
        return bool(self.errors)

    @property
    def has_warning(self) -> bool:
        return bool(self.warnings)

    @property
    def passed(self) -> bool:
        """整体是否通过：无错误即通过（警告不阻断）。"""
        return not self.has_error

    @property
    def status_text(self) -> str:
        """整体状态文字，用于界面展示。"""
        if self.has_error:
            return "校验不通过"
        if self.has_warning:
            return "校验通过（含待确认项）"
        return "校验通过"

    def to_lines(self) -> list[str]:
        return [r.to_line() for r in self.results]
