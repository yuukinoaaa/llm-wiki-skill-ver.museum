# llm-wiki-skill

`llm-wiki-skill` 用于把本地文档摄入为可浏览、可维护、互相连接的 Quartz Wiki。脚本负责稳定的机械工作，Claude Code 负责知识拆分、页面写作和互链判断。

当前版本面向“文档摄入优先”的工作流，适合把讲解词、研究材料、Markdown 笔记、文本型 PDF 等资料整理成结构化 Wiki。

## 功能

- 支持 `DOCX / PDF / MD / TXT` 文档抽取。
- 将不同格式统一为标准 JSON 文本块。
- 通过摄入计划生成 Quartz Markdown 页面。
- 支持“路线页 + 知识图谱页”结构。
- 自动补充讲解点上一页/下一页导航。
- 自动补充实体页反向链接。
- 校验 wikilink 断链、页面 frontmatter 和 manifest。
- 翻译默认关闭，中文源文档默认保持中文主文。

## 安装

需要 Python 3.11+。推荐创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果只处理 `DOCX / MD / TXT`，脚本大部分能力可使用标准库运行。`requirements.txt` 中的 `pypdf` 和 `pypinyin` 用于增强 PDF 抽取和中文标题转拼音 slug。

Quartz 需要 Node.js 18+。你可以使用已有 Quartz 项目，也可以单独初始化：

```powershell
git clone https://github.com/jackyzha0/quartz.git wiki
cd wiki
npm install
```

## 快速使用

### 1. 抽取文档

这里的 `source.docx` 是占位符，必须替换成真实文件名或真实路径。先在当前目录查看可摄入文档：

```powershell
Get-ChildItem -File -Include *.docx,*.pdf,*.md,*.txt
```

例如当前目录里有 `展览讲解词.docx`，就运行：

```powershell
python ingest_wiki.py extract ".\展览讲解词.docx" --out ".\展览讲解词.blocks.json"
```

输出文件包含：

- `source`：源文件路径、文件名、类型、SHA256。
- `blocks`：按顺序编号的文本块，如 `b0001`、`b0002`。

### 2. 让 Claude Code 生成摄入计划

`extract` 只负责把原文抽成文本块，不会自动判断哪些内容应该变成页面。下一步需要让 Claude Code 读取 `*.blocks.json`，生成一个明确的 `ingest-plan.json`。

推荐做法：

1. 让 Claude Code 读取刚生成的 `*.blocks.json`。
2. 要求它先给出摄入计划摘要，包括将创建的路线页、实体页和主要互链。
3. 你确认摘要后，再让它输出完整 JSON。
4. 将 JSON 保存为 `ingest-plan.json`。

可以直接复制这段提示词给 Claude Code：

```text
请读取 `展览讲解词.blocks.json`，为 llm-wiki 生成一个摄入计划 JSON。

要求：
- 只基于 blocks 中的内容，不联网补充。
- 中文为主文，不生成双语翻译块。
- 页面模型采用“路线页 + 知识图谱页”。
- route/stop 页面保留原文讲解顺序，并用 `stops/01-xxx.md` 这类稳定路径。
- 实体页只抽取重要对象，类型限于 exhibit / work / person / concept / place。
- 每个 stop 页通过 `outgoing_links` 指向相关实体页。
- 实体页正文要简洁，并通过 materialize 自动获得反向链接。
- 文件名使用 ASCII slug，中文标题放在 `title` 字段。
- `source_hash` 使用 blocks JSON 里的 `source.sha256`。
- `source_block_ids` 必须引用对应的 block id，例如 `b0001`。

请先输出“摄入计划摘要”，列出：
1. 预计创建的 stop 页面
2. 预计创建的实体页面
3. 关键互链
4. 可能需要人工确认的歧义

我确认后，再输出完整 `ingest-plan.json`。
```

计划结构如下：

```json
{
  "source_id": "source-demo",
  "source_hash": "abc123",
  "topic": "demo-topic",
  "pages": [
    {
      "type": "stop",
      "path": "stops/01-welcome.md",
      "title": "欢迎词",
      "body_md": "页面正文。",
      "source_block_ids": ["b0001"],
      "outgoing_links": ["works/shi-ji.md"]
    }
  ]
}
```

支持的页面类型：

| type | 用途 |
| --- | --- |
| `source` | 原始文档来源页 |
| `stop` | 讲解点、路线节点 |
| `exhibit` | 展品 |
| `work` | 典籍、作品 |
| `person` | 人物 |
| `concept` | 概念 |
| `place` | 地点 |

一个合格的摄入计划应满足：

- `path` 都是相对 `wiki/content` 的路径，不要以 `content/` 开头。
- `outgoing_links` 指向目标 Markdown 路径，例如 `works/shi-ji.md`。
- `stop` 页按浏览顺序命名，例如 `stops/01-welcome.md`、`stops/02-history.md`。
- 同一个典籍、人物或概念不要重复建页；多个讲解点都可链接到同一个实体页。
- 不确定是否应新建实体页时，先在摘要中标出，让用户确认。

### 3. Dry-run 检查

```powershell
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --dry-run
```

dry-run 只报告将创建/更新多少页面，不写入文件。

### 4. 写入 Wiki

```powershell
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --apply
```

写入位置：

- Markdown 页面：`wiki/content/...`
- manifest：`wiki/llm-wiki-manifest.json`

### 5. 校验链接

```powershell
python ingest_wiki.py validate --wiki ".\wiki"
```

校验内容：

- 页面是否有 `title` 和 `type` frontmatter。
- `[[wikilink]]` 是否指向存在的页面。
- manifest 中登记的页面是否实际存在。

### 6. 构建 HTML

```powershell
cd wiki
npx quartz build
```

Quartz 会把 `wiki/content` 中的 Markdown 构建成 HTML。

## 整体业务逻辑

### 1. 文档解析层

`llm_wiki_ingest.extractors` 负责读取 `DOCX / PDF / MD / TXT`，并统一输出文本块。每个块都有稳定编号，供后续页面追溯来源。

### 2. LLM 编排层

Claude Code 读取文本块，识别：

- 讲解点或章节顺序。
- 展品、典籍、人物、概念、地点。
- 页面之间应有的 wikilink。
- 哪些页面新建，哪些页面更新。

这一步输出 `ingest-plan.json`，脚本不直接调用模型 API。

### 3. Wiki 生成层

`materialize` 根据摄入计划写入 Quartz Markdown：

- 为讲解点页补充上一页/下一页。
- 为正文中的相关实体补充 `[[path|标题]]`。
- 为实体页补充反向链接。
- 更新 `llm-wiki-manifest.json`。

### 4. 构建层

Quartz 负责把 Markdown 构建为最终 HTML。HTML 产物不建议提交到本仓库。

## 翻译策略

翻译默认关闭。

默认配置：

```yaml
primary_engine: none
fallback_engine: none
bilingual_default: false
```

中文源文档默认不翻译，不自动生成英文或双语块。

如需翻译已有英文页面，需要显式配置：

```powershell
$env:LLM_WIKI_TRANSLATION_ENGINE = "zhipu"
$env:ZHIPU_API_KEY = "your-local-api-key"
python translate_wiki.py --content-dir ".\wiki\content" --engine zhipu
```

`translate_wiki.py` 不再包含硬编码 API key 或个人路径。

## 隐私与 Git

默认 `.gitignore` 会排除：

- 原始 `DOCX / PDF` 文档。
- 本地生成的 `wiki/`。
- 抽取出的 `*.blocks.json`。
- 本地 `config.md`。

如果源文档包含私有内容，只提交工具代码、测试、README、计划文档和配置模板。

## 测试

```powershell
python -m unittest discover -v
```

测试覆盖：

- DOCX/PDF/MD/TXT 抽取。
- slug 生成。
- 页面和 manifest 写入。
- 双向链接生成。
- 断链校验。
- 翻译默认关闭。

## 文件结构

```text
llm_wiki_ingest/
  cli.py           # 命令行入口
  extractors.py    # 文档抽取
  materialize.py   # 根据摄入计划写入 wiki
  models.py        # 数据结构
  slug.py          # slug 生成
  validate.py      # 链接和元数据校验
ingest_wiki.py     # CLI 包装脚本
translate_wiki.py  # 可选翻译工具，默认关闭
tests/             # 单元测试
docs/              # 计划和说明文档
```

## 后续方向

- 增加正式 CLI 子命令封装和更完整的错误报告。
- 为扫描版 PDF 增加 OCR 流程。
- 在用户明确授权后增加联网补充和引用校验。
- 可选增加 GitHub Pages 部署流程。
