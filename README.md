《软件工程实验》实验 6：编码规范与模块化编程
指导教师：甘文生 ｜ 网络空间安全学院 ｜ 实验地点：N516｜ 作者：昝博

学生上传论文 PDF 后，系统自动提取**文件名、文件属性、封面七项字段**，逐项与学籍库比对，
给出「**已一致 / 不一致 / 未识别**」三态结论，共 10 个检查项（R01 ~ R10）。

本仓库只包含课程设计中的**格式校验模块**，可脱离登录、数据库、上传页面单独运行与测试。

---

## 一、模块定位

| 项目 | 说明 |
|---|---|
| 所属系统 | 毕业论文提交格式合规性校验与汇交系统（7 模块之一） |
| 模块代号 | CHK（格式校验） |
| 覆盖需求 | CHK01 ~ CHK06，对应实验2《需求清单》 |
| 对外接口 | `validate`（执行全部校验）、`get_check_summary`（提供核对与台账所需的结论） |
| 不依赖什么 | 数据库、Web 框架、网络——核心逻辑只用 Python 标准库 |
| 不做什么 | 不做全文排版检查，不读取论文正文（见第八节） |

---

## 二、模块化设计（实验6 的核心）

| 设计原则 | 本模块的实现方式 | 佐证 |
|---|---|---|
| **单一职责** | 一个文件只做一件事：数据结构、判定规则、流程编排、文本归一化、相似度、封面提取、文件属性、界面 | 见第三节目录表 |
| **面向接口编程** | 引擎只依赖抽象基类 `CheckRule`，不认识任何具体规则类 | `engine.py` 中 `rule.validate(submission)` |
| **开闭原则** | 新增一类规则不需要修改引擎，只需 `register()` 一个 `CheckRule` 子类 | 测试 `test_可动态注册新规则` |
| **依赖单向无环** | `cover / models / normalizer / similarity` 无内部依赖 → `rules` → `engine`，拓扑序天然存在 | 见下方依赖图 |
| **零强制依赖** | 核心校验仅标准库；PyMuPDF 为可选增强，缺失时自动降级为「未识别」而非崩溃 | `cover.HAS_FITZ` |

模块内依赖方向（箭头 = 引用）：

```
cover        （无内部依赖）
models       （无内部依赖）
normalizer   （无内部依赖）
similarity   （无内部依赖）
   ↑
 rules  ──→  models, normalizer, similarity
   ↑
 engine ──→  models, rules
```

---

## 三、目录结构

```
ruanjiangongcheng-check/
├── app/
│   ├── __init__.py                 # 包声明
│   └── modules/
│       ├── __init__.py
│       └── check/                  # 格式校验模块
│           ├── __init__.py         # 包导出（__all__ 即对外接口白名单）
│           ├── models.py           # CheckResult / CheckReport / RuleLevel（数据结构，104 行）
│           ├── normalizer.py       # 文本归一化：全半角、空白、标点（78 行）
│           ├── similarity.py       # 相似度计算与三档分级（72 行）
│           ├── cover.py            # PDF 封面七项字段提取（177 行）
│           ├── pdfmeta.py          # 文件大小 / 扩展名 / 是否 PDF（141 行）
│           ├── rules.py            # CheckRule 抽象基类 + 3 个规则类（376 行）
│           ├── engine.py           # CheckEngine 校验引擎（101 行）
│           ├── demo.py             # 命令行演示，6 个场景（98 行）
│           └── web.py              # Flask 界面：上传 PDF 即校验（258 行）
├── tests/
│   ├── __init__.py
│   └── test_check.py               # 55 条单元测试，10 个测试类（447 行）
├── requirements.txt                # 仅界面需要 Flask
├── .gitignore
├── .gitattributes
└── README.md
```

对外只暴露 `app/modules/check/__init__.py` 的 `__all__` 中的符号，
外部模块一律 `from app.modules.check import build_default_engine`，不直接引用内部文件路径。

---

## 四、10 个检查项

| 编号 | 检查项 | 判定方式 | 不通过级别 |
|---|---|---|---|
| R01 | 文件名命名规范 | 整体一项判定：六段结构、学校代码、学号归属、`LW`、`.PDF` 大写 | 错误 |
| R02 | 文件格式 | PDF 文件头魔数 `%PDF-` | 错误 |
| R03 | 文件大小 | ≤ 30 MB 且 > 0 | 错误 |
| R04 | 论文题目 | 精确比对 + 相似度分级 | 错误 / 警告 |
| R05 | 学院 | 三态比对 | 错误 / 警告 |
| R06 | 学系 | 三态比对 | 错误 / 警告 |
| R07 | 专业 | 三态比对 | 错误 / 警告 |
| R08 | 姓名 | 三态比对 | 错误 / 警告 |
| R09 | 学号 | 三态比对 | 错误 / 警告 |
| R10 | 导师姓名 | 三态比对 | 错误 / 警告 |

### 三态判定

| 状态 | 触发条件 | 级别 |
|---|---|---|
| 已一致 | 提取值与学籍值归一化后相等 | 通过 |
| 不一致 | 两者都有值但不等 | 错误（阻断流程） |
| 未识别，请人工确认 | 封面中提取不到该字段 | 警告（不阻断，转人工核对） |

「未识别」不假装识别成功，直接标记为待人工确认——这是本模块最重要的设计取舍。

### R01 只给结论，不诊断细节

```
[错误] R01 文件名命名规范：文件名不符合命名规范，
       应为「学年_批次_学校代码_专业代码_学号_LW.PDF」，实际为「…」
```

不区分是扩展名大小写、学校代码还是学号写错——**文件名错了就是错了**，
逐项诊断只会让学生把注意力放在"改哪里"而不是"按规范重命名"。

> 注册表第六段是学号，被复制模板误用时人眼不会逐位核对，
> 一旦用了同学的文件名，论文就会归档到别人名下，所以 R01 必须校验学号归属。

### 题目的复合判定（R04）

| 情况 | 结果 |
|---|---|
| 归一化后完全相等 | 已一致 |
| 仅大小写不同 | 警告「仅大小写不同，请核对」 |
| 相似度 ≥ 0.98 | 已一致 |
| 相似度 0.80 ~ 0.98 | 警告「疑似不一致，请人工确认」 |
| 相似度 < 0.80 | 错误「与学籍登记题目不一致」 |

归一化规则：NFKC 全角转半角 → 统一中英文标点 → 去除全部空白。
因此「实验室 设备预约管理系统」与「实验室设备预约管理系统」判为一致。

---

## 五、快速开始

环境：Python 3.11+（开发环境实测 3.13.5）；Windows 下用 `py` 启动器。

```powershell
cd ruanjiangongcheng-check

# 1) 运行全部单元测试（预期 Ran 55 tests ... OK）
py -m unittest discover -s tests -t . -v

# 2) 命令行演示（6 个场景，不需要任何 PDF 文件）
py -m app.modules.check.demo

# 3) 可视化界面（需要 Flask）
py -m pip install -r requirements.txt
py -m app.modules.check.web
```

界面启动后浏览器访问 <http://127.0.0.1:5001>，选择论文 PDF → 点「开始校验」。

> 终端窗口不要关闭；看到 `Running on http://127.0.0.1:5001` 才算启动成功。

---

## 六、接口

只有一个入口函数和一条数据契约：

```python
from app.modules.check import build_default_engine

engine = build_default_engine()
report = engine.check(submission)      # submission 为数据对象（dict）

for line in report.to_lines():
    print(line)                        # 逐条打印 [通过]/[错误]/[警告]
```

### 输入：`submission`

| 键 | 类型 | 说明 |
|---|---|---|
| `file_name` | str | 上传时的原始文件名 |
| `is_pdf` | bool \| None | 内容是否为 PDF（`None` 表示未取得内容） |
| `size_mb` | float \| None | 文件大小（MB） |
| `cover` | dict \| None | 封面提取结果，键同下表的学籍字段；未识别为 `None` |
| `student` | dict | 学籍库登记值（比对基准） |

学籍字段键：`title` / `college` / `department` / `major` / `name` / `student_no` / `supervisor_name`。

### 输出：`CheckReport`

| 成员 | 说明 |
|---|---|
| `results` | 10 条 `CheckResult`（`rule_code`、`item`、`passed`、`level`、`message`） |
| `errors` / `warnings` | 未通过的错误项 / 警告项 |
| `has_error` / `passed` | 是否阻断；无错误即通过（警告不阻断） |
| `status_text` | 「校验通过」/「校验通过（含待确认项）」/「校验不通过」 |
| `to_lines()` | 渲染成多行文本，供终端或日志使用 |

---

## 七、新增一条规则（不改引擎）

```python
from app.modules.check import CheckRule, build_default_engine

class PageCountRule(CheckRule):
    """R11：页数不得少于 20 页。"""

    def validate(self, submission):
        pages = submission.get("page_count")
        if pages is None:
            return [self.fail("R11", "页数", "未取得页数")]
        if pages < 20:
            return [self.fail("R11", "页数", f"仅 {pages} 页，少于 20 页")]
        return [self.ok("R11", "页数", f"{pages} 页")]

engine = build_default_engine()
engine.register(PageCountRule())       # 引擎代码一行未改
```

引擎面向基类编程，因此新增规则只影响规则集，不影响流程编排——这是
「规则维护（RULE）模块可配置化」的实现基础（CHK06 / NFR14）。

---

## 八、测试

共 **55 条**单元测试，按被测单元分组：

| 测试类 | 用例数 | 覆盖内容 |
|---|---|---|
| `NormalizeTest` | 5 | 全半角、空白、标点、空值、大小写 |
| `SimilarityTest` | 3 | 完全相同、空值、阈值边界（0.98 / 0.80） |
| `FileNameRuleTest` | 9 | R01：合规 / 扩展名小写 / 学校代码 / 学号归属 / 结构 / 后缀 / 空值 |
| `FilePropertyRuleTest` | 6 | R02~R03：非 PDF、无内容、超限、恰好等于上限、0 字节 |
| `CoverFieldRuleTest` | 9 | R04~R10：七项通过、不一致、仅大小写、未识别、学籍缺记录、题目四级判定 |
| `EngineTest` | 8 | 规则装配、10 项齐全、整体结论、异常、动态注册 |
| `CoverParseTest` | 4 | 封面文本解析（同行 / 换行 / 不误取 / 缺字段） |
| `PdfMetaTest` | 3 | 魔数、大小与扩展名、非 PDF |
| `CoverExtractFromPdfTest` | 3 | 生成 PDF 后端到端提取（无 PyMuPDF 时跳过） |
| `WebInterfaceTest` | 5 | 首页、空提交、合规通过、小写扩展名不通过、非 PDF（无 PyMuPDF 时跳过） |

测试代码的可读性与可维护性做法：

- **用例名即需求**：`test_扩展名小写判为不通过`、`test_题目仅大小写不同为警告`
- **工厂函数**：`make_submission(**overrides)`，每条用例只写与默认值的差异
- **字面量常量化**：`STUDENT` / `OK_FILE` / `GENERIC_HINT`，改文案只改一处
- **断言公开行为**：只看 `passed`、`level`、`message` 关键字，不锁私有实现
- **环境自适应**：`@unittest.skipUnless(HAS_FITZ, ...)`，缺可选依赖时跳过而非失败

单跑某一类或某一条：

```powershell
py -m unittest tests.test_check.EngineTest -v
py -m unittest tests.test_check.FileNameRuleTest.test_扩展名小写判为不通过 -v
```

---

## 九、编码规范（本仓库自定，且已自检）

| 项目 | 做法 | 实测 |
|---|---|---|
| 命名 | 模块/函数/变量 `snake_case`；类 `PascalCase`；常量 `UPPER_CASE`；私有前缀 `_` | 一致 |
| 类型注解 | 公开函数标注参数与返回类型；文件头 `from __future__ import annotations` | 全部公开函数 |
| 文档字符串 | 模块、公开类、公开函数均有 docstring（说明用途/参数/返回/异常） | 44/51 个函数有文档（3 个 `validate()` 覆盖与 1 个嵌套辅助函数沿用基类契约，未重复书写） |
| 魔法数字 | 全部定义为模块级常量（`DEFAULT_MAX_SIZE_MB`、`TITLE_MATCH_THRESHOLD`、`KIND_SUFFIX` 等） | 无裸数字 |
| 函数长度 | 单一职责，最长 34 行 | 见 `rules.py` 题目判定 |
| 行宽 | ≤ 100 字符（`web.py` 内嵌模板样式行除外） | 最长 109（模板 CSS） |
| 导入顺序 | 标准库 → 第三方（可选）→ 本地，段间空行 | 一致 |
| 异常 | 明确抛 `ValueError` / `TypeError`；可选依赖缺失时降级 | 见 `CheckEngine` |

```powershell
py -m compileall -q app tests     # 语法与字节码检查
```

---

## 十、与课程设计文档的对应

| 文档 / 设计 | 本仓库实现 |
|---|---|
| 实验2 CHK01~CHK06 | `rules.py` 的 R01~R10；`engine.py` 汇总结论 |
| 实验4 接口 `validate` | `CheckEngine.check()` |
| 实验4 接口 `get_check_summary` | `CheckReport`（逐项结论 + 错误/警告计数） |
| 实验5 类图 `CheckRule` | `rules.CheckRule`（抽象基类 + 3 子类） |
| 实验5 类图 `CheckReport` / `CheckResult` | `models.CheckReport` / `models.CheckResult` |
| 实验6 模块化要求 | 9 个文件单职责、依赖单向无环、仅经 `__all__` 暴露 |

相对设计阶段的细化：封面七字段比对合并为单个 `CoverFieldRule`（三态判定），
并独立出 `cover.py`、`pdfmeta.py` 两个提取辅助模块——属实现阶段的合理拆分。


