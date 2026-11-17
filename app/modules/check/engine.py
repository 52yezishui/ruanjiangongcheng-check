"""校验引擎：依次执行规则并汇总结果。

引擎不关心规则如何实现，只按注册顺序调用并汇总，
对应《系统概要设计》中 19 个接口之一的 ``validate``。
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import CheckReport
from .rules import (
    DEFAULT_SCHOOL_CODE,
    CheckRule,
    CoverFieldRule,
    FileNameRule,
    FilePropertyRule,
)

__all__ = ["CheckEngine", "build_default_engine"]


class CheckEngine:
    """校验引擎。

    用法::

        engine = build_default_engine()
        report = engine.check(submission)
        for line in report.to_lines():
            print(line)

    Attributes:
        rules: 已注册的规则列表（按注册顺序执行）。
    """

    def __init__(self, rules: Iterable[CheckRule]) -> None:
        """初始化引擎。

        Args:
            rules: 规则实例的可迭代对象，至少一条。

        Raises:
            ValueError: 未提供任何规则。
        """
        self._rules: list[CheckRule] = list(rules)
        if not self._rules:
            raise ValueError("至少需要注册一条规则")

    @property
    def rules(self) -> list[CheckRule]:
        """当前已注册的规则（返回副本，外部修改不影响引擎）。"""
        return list(self._rules)

    def register(self, rule: CheckRule) -> None:
        """注册一条新规则。

        Args:
            rule: 规则实例。

        Raises:
            TypeError: 传入对象不是 :class:`CheckRule` 的子类实例。
        """
        if not isinstance(rule, CheckRule):
            raise TypeError("rule 必须是 CheckRule 的子类实例")
        self._rules.append(rule)

    def check(self, submission: dict, submission_id: str | None = None) -> CheckReport:
        """对一份提交执行全部规则。

        Args:
            submission: 提交信息字典，所需键见各规则类的 docstring。
            submission_id: 可选的提交编号，仅用于报告标识。

        Returns:
            汇总后的 :class:`CheckReport`。
        """
        report = CheckReport(submission_id=submission_id)
        for rule in self._rules:
            report.add(rule.validate(submission))
        return report


def build_default_engine(school_code: str = DEFAULT_SCHOOL_CODE) -> CheckEngine:
    """按默认配置构建引擎。

    注册 3 个规则类，共覆盖 10 个检查项（R01 ~ R10）。

    Args:
        school_code: 期望的学校代码，默认 10559。

    Returns:
        配置完成的 :class:`CheckEngine` 实例。
    """
    return CheckEngine(
        [
            FileNameRule(school_code=school_code),
            FilePropertyRule(),
            CoverFieldRule(),
        ]
    )
