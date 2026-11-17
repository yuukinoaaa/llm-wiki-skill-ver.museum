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
- 不再自动生成占位页；`outgoing_links` 指向的页面必须显式存在于计划或当前 wiki 中。
- 支持联网补充字段，由 Claude Code 检索权威来源并写入计划，脚本负责插入 Quartz callout。
- 校验 wikilink 断链、占位页残留、页面 frontmatter、manifest 和联网来源字段。
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

### 推荐流程：批量摄入 `input/`

后续所有待摄入文档默认放入仓库根目录的 `input/`。当前工具会把 `input/` 中所有 `DOCX / PDF / MD / TXT` 批量抽取为 blocks，并生成 `source-manifest.json` 供 Claude Code 分批写摄入计划。

```powershell
python ingest_wiki.py extract-dir --input ".\input" --out ".\ingest-output"
```

输出位置：

- `ingest-output/blocks/*.blocks.json`：每篇文档的标准文本块。
- `ingest-output/source-manifest.json`：输入文档清单、hash、blocks 路径、文档类型和 skipped 文件。
- `ingest-output/plans/`：建议放置 Claude Code 为每篇文档生成的局部计划。

`extract-dir` 会按 SHA256 复用未变化文件的 blocks；新增或修改的文件会重新抽取。不支持的文件会跳过并写入 `skipped`，不会中断整体流程。

可选新增 `input/input-manifest.json` 覆盖自动判断：

```json
{
  "documents": {
    "展览讲解词.docx": {
      "document_type": "script",
      "priority": 1
    },
    "某篇论文.docx": {
      "document_type": "research"
    }
  }
}
```

文档类型规则：

- `script`：讲解词，生成路线 `stops/`，保留讲解顺序。
- `research`：研究文献，生成来源页、主题页，并链接实体/概念页。
- 所有文档合并为统一 Wiki；实体页和概念页跨文档复用。

Claude Code 应按文档分批读取 `ingest-output/blocks/*.blocks.json`，把局部计划保存到 `ingest-output/plans/*.plan.json`。局部计划全部完成后合并：

```powershell
python ingest_wiki.py merge-plans ".\ingest-output\plans" --out ".\ingest-plan.json"
```

再执行 dry-run、写入、校验、构建和预览：

```powershell
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --dry-run
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --apply
python ingest_wiki.py validate --wiki ".\wiki"
python ingest_wiki.py build --wiki ".\wiki"
python ingest_wiki.py serve --wiki ".\wiki" --port 8888
```

内容比例和抽取规则：

- 默认约 75% 来自本地 input，约 25% 来自联网补充。
- 本地原文采用“较多摘录”，每页保留约 30-40% 关键原文段落，其余用整理性正文串联。
- 联网补充按需每页 0-2 条，必须使用“联网补充” callout 标注。
- 概念页采用中细粒度：有复用价值或解释价值才建页。
- 实体页采用“出现即建页”；短页至少有摘要、原文摘录和来源。
- 同义/近义概念采用“一主多别名”，只建一个主概念页并记录 `aliases`。

### 1. 让 Claude Code 生成局部摄入计划

`extract-dir` 只负责把 `input/` 下的文档批量抽成文本块，不会自动判断哪些内容应该变成页面。下一步需要让 Claude Code 按文档读取 `ingest-output/blocks/*.blocks.json`，为每篇文档生成一个局部计划，保存到 `ingest-output/plans/*.plan.json`。

推荐做法：

1. 在本仓库根目录打开 Claude Code。
2. 明确要求 Claude Code 先阅读并使用本目录下的 `SKILL.md`，按 `/llm-wiki` 的 input 批量摄入流程工作。
3. 让 Claude Code 读取 `ingest-output/source-manifest.json`，确认本轮有哪些 source。
4. 让 Claude Code 每次只处理一个 `blocks/*.blocks.json`，先输出局部计划摘要。
5. 你确认摘要后，再让它输出该文档的完整局部计划 JSON。
6. 将每篇局部计划保存为 `ingest-output/plans/<source_id>.plan.json`。

可以直接复制这段提示词给 Claude Code：

```text
请使用当前仓库中的 `SKILL.md`，按 `/llm-wiki` 的 input 批量摄入流程工作。
请先阅读 `SKILL.md`、`README.zh.md`、`ingest-output/source-manifest.json`，然后每次选择一个 `ingest-output/blocks/*.blocks.json` 生成局部摄入计划 JSON。

要求：
- 中文为主文，不生成双语翻译块。
- 所有文档最终合并为同一个统一 Wiki。
- 每篇文档必须有一个 `source` 页，路径使用 `sources/<source_id>.md`。
- 如果 `document_type` 是 `script`，保留讲解顺序并生成 `stops/01-xxx.md` 路线页。
- 如果 `document_type` 是 `research`，生成来源页、主题页，并链接相关实体/概念页。
- 实体页采用“出现即建页”，类型限于 exhibit / work / person / concept / place；短页至少包含摘要、原文摘录和来源。
- concept 采用中细粒度：有复用价值或解释价值才建页；同义/近义概念使用一个主 slug，并把其他名称放入 `aliases`。
- `type` 必须优先使用单数值：source / stop / exhibit / work / person / concept / place。
- 每个 stop 页通过 `outgoing_links` 指向相关实体页；所有目标页面必须在 `pages` 中定义，或者已经存在于 `wiki/content`。
- 文件名使用 ASCII 拼音 slug，中文标题放在 `title` 字段，例如 `concepts/diaoban-yinshua.md`。
- 不要生成英文同义重复页，例如 `printing-tech` 和 `printing-technology` 应合并为 `concepts/yinshua-jishu.md`。
- `source_hash` 使用 blocks JSON 里的 `source.sha256`。
- 多文档计划优先使用 `source_refs` 精确溯源；`source_refs[].source_id` 使用当前 source 的 `source_id`，`block_ids` 必须引用真实 block id，例如 `b0001`。
- 内容比例默认约 75% 来自本地 input、25% 来自联网补充。
- 本地原文采用“较多摘录”，每页保留约 30-40% 关键原文段落，其余用整理性正文串联。
- 默认启用联网补充，但联网检索和写作由 Claude Code 完成，脚本不直接联网。
- 检索查询只使用实体名、书名、概念名，不使用讲解词原文片段作为搜索词。
- 优先使用权威来源，`source_type` 只允许 museum / library / university / government / encyclopedia / publisher / journal / database / archive；百科只作兜底。
- 联网补充写入页面级 `web_enrichments`，每条必须有 `anchor_text`、`content_md` 和至少 1 个来源。
- `anchor_text` 必须能在页面正文中找到，materialize 会把“联网补充” callout 插入该段落后。
- 默认中等密度：stop 页每页 0-2 条，实体页和概念页每页约 1 条，不补首页 `index.md`。
- 联网补充必须明确标注为补充内容，不要把它混入讲解词原文转述。

请先输出“摄入计划摘要”，列出：
1. 当前处理的 source_id 和文档类型
2. 预计创建或复用的 source / stop / topic 页面
3. 预计创建或复用的实体页和概念页
4. 关键互链
5. 预计联网补充的页面、查询词和来源类型
6. 可能需要人工确认的歧义

我确认后，再输出该文档的完整局部计划 JSON。不要直接修改源文档，不要把 input、blocks JSON、局部计划、总计划或生成的 wiki 内容提交到 Git。
```

局部计划结构如下：

```json
{
  "source_id": "source-demo",
  "source_hash": "abc123",
  "topic": "demo-topic",
  "web_enrichment": {
    "enabled": true,
    "source_policy": "authoritative",
    "density": "medium",
    "query_policy": "entity_names_only"
  },
  "pages": [
    {
      "type": "stop",
      "path": "stops/01-welcome.md",
      "title": "欢迎词",
      "aliases": [],
      "body_md": "页面正文。",
      "source_refs": [
        {
          "source_id": "source-demo",
          "block_ids": ["b0001"],
          "quote_purpose": "excerpt"
        }
      ],
      "outgoing_links": ["works/shi-ji.md"],
      "web_enrichments": [
        {
          "anchor_text": "页面正文",
          "content_md": "这里写转述后的联网补充内容。",
          "sources": [
            {
              "title": "来源标题",
              "url": "https://example.com",
              "source_type": "library",
              "accessed_at": "2026-05-25"
            }
          ]
        }
      ]
    }
  ]
}
```

支持的页面类型：

| type        | 用途             |
| ----------- | ---------------- |
| `source`  | 原始文档来源页   |
| `stop`    | 讲解点、路线节点 |
| `exhibit` | 展品             |
| `work`    | 典籍、作品       |
| `person`  | 人物             |
| `concept` | 概念             |
| `place`   | 地点             |

一个合格的摄入计划应满足：

- `type` 优先使用单数值；工具会兼容 `concepts`、`works` 等常见复数别名，但不要主动生成复数。
- `path` 都是相对 `wiki/content` 的路径，不要以 `content/` 开头。
- `outgoing_links` 指向目标 Markdown 路径，例如 `works/shi-ji.md`。
- `outgoing_links` 不允许指向未定义页面；`materialize --dry-run` 和 `materialize --apply` 都会直接失败。
- `stop` 页按浏览顺序命名，例如 `stops/01-welcome.md`、`stops/02-history.md`。
- 同一个典籍、人物或概念不要重复建页；多个讲解点都可链接到同一个实体页。
- 概念页由 Claude Code 在摄入计划阶段生成，脚本不会自动猜测或补空概念页。
- 多文档计划优先使用 `source_refs` 精确溯源；旧字段 `source_block_ids` 仍兼容。
- 概念页可以使用 `aliases` 记录同义词，正文和链接统一指向主 slug。
- 不确定是否应新建实体页时，先在摘要中标出，让用户确认。

联网补充字段规则：

- 根级 `web_enrichment` 记录全局策略：`enabled: true`、`source_policy: authoritative`、`density: medium`、`query_policy: entity_names_only`。
- 页面级 `web_enrichments` 是数组；没有补充内容的页面可以省略该字段或设为空数组。
- 每条 `web_enrichments` 必须包含 `anchor_text`、`content_md`、`sources`。
- `sources` 中每个来源必须包含 `title`、`url`、`source_type`、`accessed_at`。
- 允许的 `source_type`：`museum`、`library`、`university`、`government`、`encyclopedia`、`publisher`、`journal`、`database`、`archive`。
- 同一页面复用同一来源时，manifest 会按标题、URL、类型和访问日期去重。

渲染效果示例：

```md
> [!info] 联网补充
> 补充内容……
>
> 来源：[来源标题](https://example.com)（library，访问：2026-05-25）
```

概念抽取不要为每篇文档硬凑数量；多文档合并后按中细粒度去重建页。优先抽取这些类型：

- 版本学：版本、写本、印本、刻本、抄本。
- 工艺：雕版印刷、活字印刷、石印、铅印、造纸技术、制墨技术、木刻水印、套色印刷。
- 分类体系：经史子集、经部、史部、子部、集部、小学。
- 文献体裁：类书、丛书、方志、家谱、舆图、校勘。
- 版本载体/形态：刻符、金文、简牍、封泥、瓦当、碑刻、包背装。

### 2. 合并局部计划

所有局部计划都保存到 `ingest-output/plans/` 后，合并为总计划：

```powershell
python ingest_wiki.py merge-plans ".\ingest-output\plans" --out ".\ingest-plan.json"
```

`merge-plans` 会合并同一路径页面的 `aliases`、`source_refs`、`outgoing_links` 和 `web_enrichments`。如果同一路径页面的 `type` 或 `title` 冲突，或者 `outgoing_links` 指向不存在页面，会直接失败。

### 3. Dry-run 检查

```powershell
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --dry-run
```

dry-run 只报告将创建/更新多少页面，不写入文件。

如果计划里的 `outgoing_links` 指向不存在的页面，dry-run 会失败并列出：

```text
Plan error: Missing outgoing link targets:
- stops/01-welcome.md -> concepts/missing-concept.md
```

这时应回到 `ingest-plan.json`，补齐对应实体页，或删除不应该存在的链接。

如果 `web_enrichments` 的 `anchor_text` 找不到、来源字段不完整，或 `source_type` 不在允许范围内，dry-run 也会失败。先修计划，再 apply。

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
- 是否还残留旧版本 `materialize` 自动生成的占位页。
- manifest 中登记的页面是否实际存在。
- manifest 中的 `web_sources` 字段是否完整，`source_type` 是否属于允许的权威来源类型。

### 6. 清理旧占位页

如果你之前用旧版本工具生成过 wiki，可能会留下自动占位页。先 dry-run 查看：

```powershell
python ingest_wiki.py clean-stubs --wiki ".\wiki" --dry-run
```

确认后删除：

```powershell
python ingest_wiki.py clean-stubs --wiki ".\wiki" --apply
```

该命令只删除包含固定占位标记的 Markdown 页面，不会删除正常页面。删除后需要修复 `ingest-plan.json` 中指向这些页面的链接，或为它们补充正式实体页，再重新执行 `materialize --apply` 和 `validate`。

### 7. 构建 HTML

```powershell
python ingest_wiki.py build --wiki ".\wiki"
```

Quartz 会把 `wiki/content` 中的 Markdown 构建成 HTML。

### 8. 本地预览 HTML

不要直接用 `python -m http.server` 预览 Quartz 输出。Quartz 页面链接通常是 clean URL，例如 `/exhibits/changsheng-wuji-wadang`，但普通 `http.server` 不会自动映射到 `exhibits/changsheng-wuji-wadang.html`，具体页面容易 404。

请回到本仓库根目录运行：

```powershell
python ingest_wiki.py serve --wiki ".\wiki" --port 8888
```

然后打开：

```text
http://127.0.0.1:8888/
```

具体页面可以用 clean URL：

```text
http://127.0.0.1:8888/exhibits/changsheng-wuji-wadang
```

如果你当前已经 `cd wiki`，请使用：

```powershell
python ..\ingest_wiki.py serve --wiki "." --port 8888
```

## 整体业务逻辑

### 1. 文档解析层

`llm_wiki_ingest.extractors` 负责读取 `DOCX / PDF / MD / TXT`，并统一输出文本块。每个块都有稳定编号，供后续页面追溯来源。

### 2. LLM 编排层

Claude Code 读取文本块，识别：

- 讲解点或章节顺序。
- 展品、典籍、人物、概念、地点。
- 页面之间应有的 wikilink。
- 哪些页面新建，哪些页面更新。
- 需要联网补充的位置、查询词、权威来源和补充正文。

这一步输出 `ingest-plan.json`，脚本不直接调用模型 API。

联网补充也发生在这一层：Claude Code 负责用实体名、书名或概念名检索并转述权威来源；脚本只消费计划中的结构化 `web_enrichments`，不自己联网搜索。

### 3. Wiki 生成层

`materialize` 根据摄入计划写入 Quartz Markdown：

- 为讲解点页补充上一页/下一页。
- 为正文中的相关实体补充 `[[path|标题]]`。
- 为实体页补充反向链接。
- 检查 `outgoing_links` 是否都指向真实页面；不会自动创建占位页。
- 根据 `anchor_text` 把联网补充插入正文附近的 Quartz callout。
- 将外部来源写入 manifest 的 `web_sources`，同页去重。
- 更新 `llm-wiki-manifest.json`。

### 4. 构建层

Quartz 负责把 Markdown 构建为最终 HTML。HTML 产物不建议提交到本仓库。

## 联网补充策略

联网补充默认开启，但由 Claude Code 完成检索与写作，脚本不直接联网。这样可以把搜索判断、来源筛选和转述质量留给 LLM 编排层，同时让脚本保持可测试、可复现。

规则：

- 查询只使用实体名、书名、概念名，不使用讲解词原文片段。
- 优先来源：博物馆、图书馆、高校、政府、出版社；百科只作兜底。
- 补充内容必须使用“联网补充” callout 标注，不混入原文主体。
- 内容以转述为主，短引文必须克制并带来源。
- `validate` 只检查来源字段完整性和类型合法性，不联网验证 URL 可访问性。

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
- 本地 `input/`。
- 本地 `ingest-output/`。
- 本地生成的 `wiki/`。
- 抽取出的 `*.blocks.json`。
- 本地 `config.md`。

如果源文档包含私有内容，只提交工具代码、README、计划文档和配置模板。`tests/` 只保留在本地验证，不推送 GitHub。

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
- 占位页清理与占位页残留校验。
- 联网补充 callout 插入。
- manifest `web_sources` 写入、去重和字段校验。
- `extract-dir`、`merge-plans`、`build` 批量流程。
- `source_refs` 与 `aliases`。
- 翻译默认关闭。

## 文件结构

```text
llm_wiki_ingest/
  cli.py           # 命令行入口
  batch_extract.py # input 目录批量抽取
  build.py         # Quartz build 包装
  extractors.py    # 文档抽取
  materialize.py   # 根据摄入计划写入 wiki
  merge_plans.py   # 局部计划合并
  models.py        # 数据结构
  slug.py          # slug 生成
  stubs.py         # 旧占位页识别与清理
  web_enrichment.py # 联网补充来源类型和去重规则
  validate.py      # 链接和元数据校验
ingest_wiki.py     # CLI 包装脚本
translate_wiki.py  # 可选翻译工具，默认关闭
tests/             # 本地单元测试，默认不推送 GitHub
docs/              # 计划和说明文档
```

## 后续方向

- 增加正式 CLI 子命令封装和更完整的错误报告。
- 为扫描版 PDF 增加 OCR 流程。
- 增加可选 URL 可达性检查和更细的来源质量报告。
- 可选增加 GitHub Pages 部署流程。
