"""格式校验模块的可视化界面（Flask）。

本界面是校验模块的演示外壳，不含业务逻辑：
文件属性提取交给 :mod:`pdfmeta`，封面字段提取交给 :mod:`cover`，
判定全部委托给 :func:`engine.build_default_engine`。

使用方式：上传论文 PDF → 点「开始校验」→ 查看 10 项结果。

运行方式::

    py -m app.modules.check.web

然后浏览器访问 http://127.0.0.1:5001
"""

from __future__ import annotations

from flask import Flask, render_template_string, request

from .cover import COVER_FIELDS, extract_cover_fields
from .engine import build_default_engine
from .models import CheckResult
from .pdfmeta import extract_file_info, looks_like_pdf
from .rules import FILENAME_TEMPLATE

__all__ = ["app"]

# ---------------------------------------------------------------------------
# 学籍库基准数据（演示用，实际系统中从数据库读取）
# ---------------------------------------------------------------------------
BASE_STUDENT: dict[str, str] = {
    "title": "基于同态加密的医疗数据隐私保护预测系统（HE-MedPrivacy）",
    "college": "网络空间安全学院",
    "department": "网络空间安全系",
    "major": "信息安全",
    "name": "张家瑜",
    "student_no": "2022102893",
    "supervisor_name": "甘文生",
}

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>毕业论文提交格式合规性校验</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 28px;
    font-family: "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
    background: #f4f6f8; color: #1f2328; font-size: 14px;
  }
  .wrap { max-width: 1080px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #656d76; font-size: 12px; margin-bottom: 18px; }
  .card {
    background: #fff; border: 1px solid #d0d7de; border-radius: 6px;
    padding: 16px 20px; margin-bottom: 16px;
  }
  .card h2 { font-size: 14px; margin: 0 0 12px; padding-bottom: 8px; border-bottom: 1px solid #eaeef2; }
  .ro { color: #656d76; font-size: 12.5px; line-height: 2; }
  .ro b { color: #1f2328; }
  form { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
  input[type=file] { font-size: 13px; padding: 6px; border: 1px solid #d0d7de;
                     border-radius: 4px; background: #f6f8fa; }
  button { padding: 8px 22px; border-radius: 4px; border: 1px solid #1a7f37;
           background: #1f883d; color: #fff; font-size: 13px; font-weight: 600;
           cursor: pointer; font-family: inherit; }
  button:hover { filter: brightness(0.96); }
  code { background: #f6f8fa; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
  .banner { padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 16px; }
  .banner.err { background: #ffebe9; border: 1px solid #cf222e55; color: #cf222e; }
  .verdict { display: flex; gap: 16px; align-items: center; padding: 12px 16px; border-radius: 6px; }
  .verdict.ok  { background: #dafbe1; border: 1px solid #1f883d55; }
  .verdict.warn{ background: #fff8c5; border: 1px solid #d4a72c55; }
  .verdict.err { background: #ffebe9; border: 1px solid #cf222e55; }
  .verdict b { font-size: 16px; }
  .stat { font-size: 13px; color: #656d76; }
  .src { background: #f6f8fa; border: 1px solid #eaeef2; border-radius: 4px;
         padding: 10px 14px; font-size: 12.5px; color: #656d76; line-height: 1.9; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border-bottom: 1px solid #eaeef2; padding: 8px; text-align: left; vertical-align: top; }
  th { background: #f6f8fa; font-weight: 600; font-size: 12px; color: #656d76; }
  td.c { text-align: center; white-space: nowrap; }
  tr.ok td.c { color: #1a7f37; }
  tr.err td.c { color: #cf222e; font-weight: 600; }
  tr.warn td.c { color: #9a6700; font-weight: 600; }
  tr.err { background: #fff8f8; }
  tr.warn { background: #fffdf5; }
</style>
</head>
<body>
<div class="wrap">
  <h1>毕业论文提交格式合规性校验</h1>
  <div class="sub">《软件工程实验》实验6 核心模块演示 ｜ 上传 PDF 后自动提取封面字段并逐项比对，共 10 个检查项</div>

  {% if error %}
  <div class="banner err">{{ error }}</div>
  {% endif %}

  <div class="card">
    <h2>学籍库登记信息（比对基准）</h2>
    <div class="ro">
      <b>论文题目：</b>{{ student.title }}<br>
      <b>学院：</b>{{ student.college }}　<b>学系：</b>{{ student.department }}　<b>专业：</b>{{ student.major }}<br>
      <b>姓名：</b>{{ student.name }}　<b>学号：</b>{{ student.student_no }}　<b>导师：</b>{{ student.supervisor_name }}
    </div>
  </div>

  <div class="card">
    <h2>上传论文文件</h2>
    <div class="ro">
      命名规范：<code>{{ filename_template }}</code><br>
      例如：<code>2526_44_10559_080904K_{{ student.student_no }}_LW.PDF</code>
      （扩展名必须为大写 <code>.PDF</code>）
    </div>
    <form method="post" action="/check" enctype="multipart/form-data">
      <input type="file" name="pdf_file" accept=".pdf,.PDF" required>
      <button type="submit">开始校验</button>
    </form>
  </div>

  {% if report %}
  <div class="card">
    <h2>校验结果
      <span class="stat">—— {{ report.total }} 项，通过 {{ report.passed_count }} 项，
        错误 {{ report.error_count }} 项，警告 {{ report.warning_count }} 项</span>
    </h2>
    <div class="src">
      文件名 <b>{{ report.file_name }}</b>　大小 {{ report.size_mb }} MB<br>
      {{ report.extract_note }}
    </div>
    <div class="verdict {{ report.cls }}" style="margin-top:12px">
      <b>{{ report.status }}</b>
      <span class="stat">{{ report.advice }}</span>
    </div>
    <table style="margin-top:12px">
      <thead>
        <tr><th style="width:6%">编号</th><th style="width:22%">检查项</th>
            <th style="width:10%">状态</th><th>说明</th></tr>
      </thead>
      <tbody>
        {% for r in report.rows %}
        <tr class="{{ r.cls }}">
          <td class="c">{{ r.code }}</td>
          <td>{{ r.item }}</td>
          <td class="c">{{ r.status }}</td>
          <td>{{ r.message or '—' }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>
</body>
</html>
"""

app = Flask(__name__)


def _submission_from_upload(raw: bytes, file_name: str) -> tuple[dict, str]:
    """从上传文件构造提交信息。

    Returns:
        ``(submission, 提取说明)``。
    """
    info = extract_file_info(file_name, raw)
    cover = extract_cover_fields(raw)
    submission = {
        "file_name": info.file_name,
        "is_pdf": looks_like_pdf(raw),
        "size_mb": info.size_mb,
        "cover": cover.fields,
        "student": dict(BASE_STUDENT),
    }
    if not cover.available:
        note = f"封面字段提取不可用：{cover.reason}"
    else:
        note = f"封面字段识别 {cover.recognized_count} / {len(COVER_FIELDS)} 项"
        missing = cover.missing()
        if missing:
            note += "；未识别：" + "、".join(missing)
    return submission, note


def _row_class(result: CheckResult) -> str:
    """根据结果确定表格行的样式类名。"""
    if result.passed:
        return "ok"
    return "err" if result.level.value == "错误" else "warn"


def _render(report: dict[str, object] | None = None, error: str = "") -> str:
    """渲染页面。"""
    return render_template_string(
        PAGE_TEMPLATE,
        report=report,
        error=error,
        student=BASE_STUDENT,
        filename_template=FILENAME_TEMPLATE,
    )


def _run_check(submission: dict, note: str) -> dict[str, object]:
    """执行校验并整理成视图模型。"""
    report = build_default_engine().check(submission)
    rows = [
        {
            "code": r.rule_code,
            "item": r.item,
            "status": r.status_text,
            "message": r.message,
            "cls": _row_class(r),
        }
        for r in report.results
    ]
    if report.has_error:
        status_cls, advice = "err", "存在错误项，已阻断流程，请修正后重新提交"
    elif report.has_warning:
        status_cls, advice = "warn", "无阻断性错误，警告项需人工确认"
    else:
        status_cls, advice = "ok", "可以进入导师确认环节"
    return {
        "rows": rows,
        "total": len(rows),
        "passed_count": sum(1 for r in report.results if r.passed),
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "status": report.status_text,
        "cls": status_cls,
        "advice": advice,
        "file_name": submission.get("file_name") or "—",
        "size_mb": f"{float(submission.get('size_mb') or 0):.2f}",
        "extract_note": note,
    }


@app.get("/")
def index() -> str:
    """展示上传页。"""
    return _render()


@app.post("/check")
def check() -> str:
    """执行校验并展示结果。"""
    upload = request.files.get("pdf_file")
    if upload is None or not upload.filename:
        return _render(error="请先选择要校验的论文 PDF 文件")

    submission, note = _submission_from_upload(upload.read(), upload.filename)
    return _render(_run_check(submission, note))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
