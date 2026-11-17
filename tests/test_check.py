"""格式校验模块的单元测试（实验6 / 实验8 通用）。

运行方式::

    py -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import io
import unittest

from app.modules.check import (
    COVER_FIELDS,
    CheckEngine,
    CoverFieldRule,
    FileNameRule,
    FilePropertyRule,
    RuleLevel,
    build_default_engine,
    classify,
    extract_cover_fields,
    extract_file_info,
    looks_like_pdf,
    normalize,
    normalize_case_insensitive,
    similarity,
)
from app.modules.check.cover import HAS_FITZ, parse_cover_text
from app.modules.check.rules import EXTENSION, KIND_SUFFIX

STUDENT = {
    "title": "基于同态加密的医疗数据隐私保护预测系统（HE-MedPrivacy）",
    "college": "网络空间安全学院",
    "department": "网络空间安全系",
    "major": "信息安全",
    "name": "张家瑜",
    "student_no": "2022102893",
    "supervisor_name": "甘文生",
}
OK_FILE = "2526_44_10559_080904K_2022102893_LW.PDF"
GENERIC_HINT = "文件名不符合命名规范"


def make_submission(**overrides: object) -> dict:
    """构造一份默认全部合规的提交信息，便于逐项覆盖。"""
    base: dict[str, object] = {
        "file_name": OK_FILE,
        "is_pdf": True,
        "size_mb": 3.2,
        "cover": dict(STUDENT),
        "student": dict(STUDENT),
    }
    base.update(overrides)
    return base


def codes(results: list) -> list[str]:
    """取出结果中的检查项编号。"""
    return [r.rule_code for r in results]


def by_code(results: list, code: str):
    """按编号取出结果。"""
    return [r for r in results if r.rule_code == code][0]


class NormalizeTest(unittest.TestCase):
    """归一化函数测试。"""

    def test_全角转半角(self):
        self.assertEqual(normalize("ＡＢＣ"), "ABC")

    def test_去除全部空白(self):
        self.assertEqual(normalize(" 毕业 论文\t设计\n"), "毕业论文设计")

    def test_中文标点统一(self):
        self.assertEqual(normalize("论文（终稿）。"), "论文(终稿).")

    def test_空值返回空串(self):
        self.assertEqual(normalize(None), "")
        self.assertEqual(normalize("   "), "")

    def test_忽略大小写归一化(self):
        self.assertEqual(
            normalize_case_insensitive("HE-MedPrivacy"),
            normalize_case_insensitive("he-medprivacy"),
        )


class SimilarityTest(unittest.TestCase):
    """相似度与分级判定测试。"""

    def test_完全相同为一(self):
        self.assertEqual(similarity("abc", "abc"), 1.0)

    def test_任一为空为零(self):
        self.assertEqual(similarity("", "abc"), 0.0)

    def test_阈值边界(self):
        self.assertEqual(classify(0.98), "一致")
        self.assertEqual(classify(0.9799), "疑似不一致")
        self.assertEqual(classify(0.80), "疑似不一致")
        self.assertEqual(classify(0.7999), "不一致")


class FileNameRuleTest(unittest.TestCase):
    """R01 文件名命名规范测试（整体一项，不诊断细节）。"""

    def test_合规文件名通过且只产生一项(self):
        results = FileNameRule().validate(make_submission())
        self.assertEqual(codes(results), ["R01"])
        self.assertTrue(results[0].passed)

    def test_扩展名小写判为不通过(self):
        results = FileNameRule().validate(make_submission(file_name=OK_FILE[:-3] + "pdf"))
        self.assertFalse(results[0].passed)
        self.assertIn(GENERIC_HINT, results[0].message)

    def test_学校代码错误(self):
        bad = OK_FILE.replace("_10559_", "_10558_")
        results = FileNameRule().validate(make_submission(file_name=bad))
        self.assertFalse(results[0].passed)
        self.assertIn(GENERIC_HINT, results[0].message)

    def test_学号不是本人(self):
        bad = OK_FILE.replace("2022102893", "2022100000")
        results = FileNameRule().validate(make_submission(file_name=bad))
        self.assertFalse(results[0].passed)
        self.assertIn(GENERIC_HINT, results[0].message)

    def test_结构不符(self):
        results = FileNameRule().validate(make_submission(file_name="毕业论文.pdf"))
        self.assertFalse(results[0].passed)

    def test_类型后缀错误(self):
        bad = OK_FILE.replace("_LW.", "_XW.")
        results = FileNameRule().validate(make_submission(file_name=bad))
        self.assertFalse(results[0].passed)

    def test_文件名为空(self):
        results = FileNameRule().validate(make_submission(file_name=""))
        self.assertFalse(results[0].passed)

    def test_学籍无学号时跳过归属校验(self):
        empty_student = dict(STUDENT, student_no="")
        results = FileNameRule().validate(make_submission(student=empty_student))
        self.assertTrue(results[0].passed)

    def test_常量与规范一致(self):
        self.assertEqual(KIND_SUFFIX, "LW")
        self.assertEqual(EXTENSION, "PDF")


class FilePropertyRuleTest(unittest.TestCase):
    """R02 ~ R03 文件属性测试。"""

    def test_全部通过(self):
        results = FilePropertyRule().validate(make_submission())
        self.assertEqual(codes(results), ["R02", "R03"])
        self.assertTrue(all(r.passed for r in results))

    def test_不是PDF(self):
        results = FilePropertyRule().validate(make_submission(is_pdf=False))
        self.assertEqual([r.rule_code for r in results if not r.passed], ["R02"])

    def test_未取得文件内容(self):
        results = FilePropertyRule().validate(make_submission(is_pdf=None))
        self.assertEqual([r.rule_code for r in results if not r.passed], ["R02"])

    def test_超限(self):
        results = FilePropertyRule().validate(make_submission(size_mb=42))
        self.assertEqual([r.rule_code for r in results if not r.passed], ["R03"])

    def test_边界值_恰好等于上限通过(self):
        results = FilePropertyRule(max_size_mb=30).validate(make_submission(size_mb=30))
        self.assertTrue(all(r.passed for r in results))

    def test_大小为零判为异常(self):
        results = FilePropertyRule().validate(make_submission(size_mb=0))
        self.assertEqual([r.rule_code for r in results if not r.passed], ["R03"])


class CoverFieldRuleTest(unittest.TestCase):
    """R04 ~ R10 封面字段三态比对测试。"""

    def test_七项全部通过(self):
        results = CoverFieldRule().validate(make_submission())
        self.assertEqual(codes(results), ["R04", "R05", "R06", "R07", "R08", "R09", "R10"])
        self.assertTrue(all(r.passed for r in results))

    def test_姓名不一致为错误(self):
        cover = dict(STUDENT, name="张三")
        results = CoverFieldRule().validate(make_submission(cover=cover))
        item = by_code(results, "R08")
        self.assertFalse(item.passed)
        self.assertIs(item.level, RuleLevel.ERROR)
        self.assertIn("张家瑜", item.message)

    def test_专业仅大小写不同单独提示(self):
        student = dict(STUDENT, major="Information Security")
        cover = dict(STUDENT, major="information security")
        results = CoverFieldRule().validate(make_submission(cover=cover, student=student))
        item = by_code(results, "R07")
        self.assertFalse(item.passed)
        self.assertIn("仅大小写不一致", item.message)

    def test_导师未识别为警告(self):
        cover = dict(STUDENT, supervisor_name=None)
        results = CoverFieldRule().validate(make_submission(cover=cover))
        item = by_code(results, "R10")
        self.assertFalse(item.passed)
        self.assertIs(item.level, RuleLevel.WARNING)
        self.assertIn("未识别", item.message)

    def test_学籍缺记录为警告(self):
        student = dict(STUDENT, college="")
        results = CoverFieldRule().validate(make_submission(student=student))
        item = by_code(results, "R05")
        self.assertFalse(item.passed)
        self.assertIs(item.level, RuleLevel.WARNING)

    def test_题目完全一致通过(self):
        results = CoverFieldRule().validate(make_submission())
        self.assertTrue(by_code(results, "R04").passed)

    def test_题目仅大小写不同为警告(self):
        cover = dict(STUDENT, title="基于同态加密的医疗数据隐私保护预测系统（he-medprivacy）")
        results = CoverFieldRule().validate(make_submission(cover=cover))
        item = by_code(results, "R04")
        self.assertFalse(item.passed)
        self.assertIs(item.level, RuleLevel.WARNING)
        self.assertIn("仅大小写不同", item.message)

    def test_题目疑似不一致为警告(self):
        cover = dict(STUDENT, title=STUDENT["title"] + "研究")
        results = CoverFieldRule().validate(make_submission(cover=cover))
        item = by_code(results, "R04")
        self.assertFalse(item.passed)
        self.assertIs(item.level, RuleLevel.WARNING)
        self.assertIn("疑似不一致", item.message)

    def test_题目完全不一致为错误(self):
        cover = dict(STUDENT, title="一个完全无关的题目名称")
        results = CoverFieldRule().validate(make_submission(cover=cover))
        item = by_code(results, "R04")
        self.assertFalse(item.passed)
        self.assertIs(item.level, RuleLevel.ERROR)


class EngineTest(unittest.TestCase):
    """校验引擎测试。"""

    def test_默认引擎注册三个规则类(self):
        self.assertEqual(len(build_default_engine().rules), 3)

    def test_默认引擎共十个检查项(self):
        report = build_default_engine().check(make_submission())
        self.assertEqual(len(report.results), 10)
        self.assertEqual(codes(report.results), [f"R{i:02d}" for i in range(1, 11)])

    def test_全部合规时无错误无警告(self):
        report = build_default_engine().check(make_submission())
        self.assertFalse(report.has_error)
        self.assertFalse(report.has_warning)
        self.assertEqual(report.status_text, "校验通过")

    def test_存在警告时整体仍通过(self):
        cover = dict(STUDENT, supervisor_name=None)
        report = build_default_engine().check(make_submission(cover=cover))
        self.assertFalse(report.has_error)
        self.assertTrue(report.has_warning)
        self.assertTrue(report.passed)

    def test_存在错误时整体不通过(self):
        report = build_default_engine().check(make_submission(size_mb=99))
        self.assertTrue(report.has_error)
        self.assertEqual(report.status_text, "校验不通过")

    def test_无规则时抛异常(self):
        with self.assertRaises(ValueError):
            CheckEngine([])

    def test_注册非规则对象抛异常(self):
        with self.assertRaises(TypeError):
            build_default_engine().register(object())  # type: ignore[arg-type]

    def test_可动态注册新规则(self):
        engine = CheckEngine([FileNameRule()])
        before = len(engine.check(make_submission()).results)
        engine.register(FilePropertyRule())
        after = len(engine.check(make_submission()).results)
        self.assertEqual(after - before, 2)


class CoverParseTest(unittest.TestCase):
    """封面文本解析测试（不依赖 PDF 文件）。"""

    def test_标签与值同行(self):
        text = "论文题目    基于同态加密的医疗数据\n学    院    网络空间安全学院"
        fields = parse_cover_text(text)
        self.assertEqual(fields["title"], "基于同态加密的医疗数据")
        self.assertEqual(fields["college"], "网络空间安全学院")

    def test_标签后无值取下一行(self):
        text = "指导教师\n甘文生\n学号\n2022102893"
        fields = parse_cover_text(text)
        self.assertEqual(fields["supervisor_name"], "甘文生")
        self.assertEqual(fields["student_no"], "2022102893")

    def test_下一行是标签时不误取(self):
        text = "指导教师\n学号\n2022102893"
        fields = parse_cover_text(text)
        self.assertIsNone(fields["supervisor_name"])
        self.assertEqual(fields["student_no"], "2022102893")

    def test_未出现的字段为None(self):
        fields = parse_cover_text("只有一些无关文字")
        self.assertTrue(all(value is None for value in fields.values()))
        self.assertEqual(len(fields), len(COVER_FIELDS))


class PdfMetaTest(unittest.TestCase):
    """PDF 属性提取测试。"""

    def test_魔数判断(self):
        self.assertTrue(looks_like_pdf(b"%PDF-1.4 ..."))
        self.assertFalse(looks_like_pdf(b"PK\x03\x04"))

    def test_提取大小与扩展名(self):
        info = extract_file_info(OK_FILE, b"%PDF-1.4" + b"0" * 1024)
        self.assertEqual(info.extension, ".pdf")
        self.assertGreater(info.size_mb, 0)
        self.assertTrue(info.is_pdf)

    def test_非PDF(self):
        info = extract_file_info("a.docx", b"PK\x03\x04")
        self.assertFalse(info.is_pdf)


@unittest.skipUnless(HAS_FITZ, "未安装 PyMuPDF，跳过真实 PDF 解析测试")
class CoverExtractFromPdfTest(unittest.TestCase):
    """封面提取端到端测试（生成 PDF 后提取）。"""

    @staticmethod
    def build_pdf(rows: list[tuple[str, str]] | None = None) -> bytes:
        """生成一份带封面的 PDF。"""
        import fitz

        rows = rows or [
            ("论文题目", STUDENT["title"]),
            ("学    院", STUDENT["college"]),
            ("学    系", STUDENT["department"]),
            ("专    业", STUDENT["major"]),
            ("姓    名", STUDENT["name"]),
            ("学    号", STUDENT["student_no"]),
            ("指导教师", STUDENT["supervisor_name"]),
        ]
        doc = fitz.open()
        page = doc.new_page()
        y = 120
        for label, value in rows:
            page.insert_text((72, y), f"{label}    {value}", fontname="china-s", fontsize=12)
            y += 36
        data = doc.tobytes()
        doc.close()
        return data

    def test_七个字段全部识别(self):
        extraction = extract_cover_fields(self.build_pdf())
        self.assertTrue(extraction.available, extraction.reason)
        self.assertEqual(extraction.recognized_count, len(COVER_FIELDS))
        self.assertEqual(extraction.fields["name"], STUDENT["name"])
        self.assertEqual(extraction.fields["supervisor_name"], STUDENT["supervisor_name"])
        self.assertEqual(extraction.fields["student_no"], STUDENT["student_no"])

    def test_非PDF返回不可用(self):
        extraction = extract_cover_fields(b"not a pdf")
        self.assertFalse(extraction.available)
        self.assertEqual(extraction.recognized_count, 0)

    def test_缺少导师时只该项未识别(self):
        rows = [
            ("论文题目", STUDENT["title"]),
            ("学    院", STUDENT["college"]),
            ("姓    名", STUDENT["name"]),
        ]
        extraction = extract_cover_fields(self.build_pdf(rows))
        self.assertTrue(extraction.available)
        self.assertIsNone(extraction.fields["supervisor_name"])
        self.assertIn("导师姓名", extraction.missing())


@unittest.skipUnless(HAS_FITZ, "未安装 PyMuPDF，跳过上传测试")
class WebInterfaceTest(unittest.TestCase):
    """Web 界面冒烟测试（仅上传 PDF 一条路径）。"""

    def setUp(self) -> None:
        from app.modules.check.web import app

        app.config.update(TESTING=True)
        self.client = app.test_client()

    def _post(self, file_name: str, content: bytes):
        """提交一个上传请求。"""
        return self.client.post(
            "/check",
            data={"pdf_file": (io.BytesIO(content), file_name)},
            content_type="multipart/form-data",
        )

    def test_首页可访问且无演示场景按钮(self):
        resp = self.client.get("/")
        text = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("毕业论文提交格式合规性校验", text)
        self.assertIn("上传论文文件", text)
        self.assertNotIn("演示场景", text)

    def test_未选文件时给出提示(self):
        resp = self.client.post("/check", data={}, content_type="multipart/form-data")
        text = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("请先选择要校验的论文 PDF 文件", text)

    def test_上传合规PDF通过校验(self):
        resp = self._post(OK_FILE, CoverExtractFromPdfTest.build_pdf())
        text = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("10 项", text)
        self.assertIn("校验通过", text)
        self.assertIn(STUDENT["name"], text)

    def test_上传小写扩展名判不通过(self):
        resp = self._post(OK_FILE[:-3] + "pdf", CoverExtractFromPdfTest.build_pdf())
        text = resp.get_data(as_text=True)
        self.assertIn("文件名不符合命名规范", text)
        self.assertIn("校验不通过", text)

    def test_上传非PDF内容时格式检查不通过(self):
        resp = self._post(OK_FILE, b"this is not a pdf")
        text = resp.get_data(as_text=True)
        self.assertIn("文件内容不是 PDF", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
