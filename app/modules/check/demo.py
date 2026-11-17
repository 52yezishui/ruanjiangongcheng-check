"""格式校验模块的命令行演示。

无需数据库、无需 Web 框架，直接运行::

    py -m app.modules.check.demo

说明：为便于在无 PDF 文件的环境下运行，本脚本直接给出
「封面提取后的字段值」，模拟封面提取的结果；真实的 PDF 提取
请使用可视化界面（``py -m app.modules.check.web``）上传文件。
"""

from __future__ import annotations

from .engine import build_default_engine
from .models import CheckReport

__all__ = ["CASES", "BASE_STUDENT", "run_case", "main"]

BASE_STUDENT: dict[str, str] = {
    "title": "基于同态加密的医疗数据隐私保护预测系统（HE-MedPrivacy）",
    "college": "网络空间安全学院",
    "department": "网络空间安全系",
    "major": "信息安全",
    "name": "张家瑜",
    "student_no": "2022102893",
    "supervisor_name": "甘文生",
}

OK_FILE = "2526_44_10559_080904K_2022102893_LW.PDF"


def _case(name: str, file_name: str, cover_overrides: dict, **overrides: object) -> dict:
    """构造一个演示场景。"""
    cover = dict(BASE_STUDENT)
    cover.update(cover_overrides)
    submission: dict[str, object] = {
        "file_name": file_name,
        "is_pdf": True,
        "size_mb": 3.2,
        "cover": cover,
        "student": dict(BASE_STUDENT),
    }
    submission.update(overrides)
    return {"name": name, "submission": submission}


#: 演示场景：覆盖全部合规、错误、警告三种结论。
CASES: list[dict] = [
    _case("场景 1：全部合规", OK_FILE, {}),
    _case("场景 2：扩展名写成小写 .pdf", OK_FILE[:-3] + "pdf", {}),
    _case("场景 3：文件名学号不是本人", OK_FILE.replace("2022102893", "2022100000"), {}),
    _case(
        "场景 4：题目仅大小写不同",
        OK_FILE,
        {"title": "基于同态加密的医疗数据隐私保护预测系统（he-medprivacy）"},
    ),
    _case("场景 5：导师姓名未识别（转人工确认）", OK_FILE, {"supervisor_name": ""}),
    _case(
        "场景 6：封面信息错配 + 文件超限",
        OK_FILE,
        {"name": "张三", "major": "网络工程"},
        size_mb=42.5,
    ),
]


def run_case(submission: dict) -> CheckReport:
    """对单个提交执行校验。

    Args:
        submission: 提交信息字典。

    Returns:
        校验报告。
    """
    return build_default_engine().check(submission)


def main() -> None:
    """依次运行全部演示场景并打印结果。"""
    engine = build_default_engine()
    print(f"校验引擎已注册 {len(engine.rules)} 个规则类，共 10 个检查项\n")

    for case in CASES:
        report = run_case(case["submission"])
        print("=" * 70)
        print(case["name"])
        print("=" * 70)
        for line in report.to_lines():
            print("  " + line)
        print(
            f"  → {report.status_text}"
            f"（错误 {len(report.errors)} 项，警告 {len(report.warnings)} 项）\n"
        )


if __name__ == "__main__":
    main()
