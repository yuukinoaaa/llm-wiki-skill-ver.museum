# LLM Wiki input 批量摄入计划

## 当前目标

将 `input/` 作为后续唯一输入目录，把其中所有 `DOCX / PDF / MD / TXT` 批量摄入为同一个 Quartz Wiki。脚本负责批量抽取、局部计划合并、落盘、校验和构建；Claude Code 负责按文档生成局部计划、页面写作、实体/概念拆分和联网补充。

当前本地 `input/` 中的 8 个 `.docx` 都参与摄入。`input/`、`ingest-output/`、`ingest-plan.json`、`wiki/` 和 HTML 构建产物均为私有本地产物，不进入 GitHub。

## 决策清单

| 决策 | 当前选择 |
| --- | --- |
| 输入目录 | `input/` |
| 输出抽取目录 | `ingest-output/` |
| Wiki 结构 | 统一知识库，实体/概念跨文档复用 |
| 文档模型 | 讲解词生成 `stops/` 路线；研究文献生成 `sources/` 和主题内容 |
| 内容比例 | 约 75% 本地 input，25% 联网补充 |
| 原文摘录 | 每页约 30-40% 关键原文段落 |
| 概念粒度 | 中细粒度，有复用或解释价值才建页 |
| 实体粒度 | 出现即建页，但短页必须有摘要、摘录和来源 |
| 同义词 | 一主多别名，使用 `aliases` |
| 来源引用 | 新增结构化 `source_refs`，兼容旧 `source_block_ids` |
| 联网来源 | 中文权威优先，可使用外文权威来源 |
| source_type | `museum`、`library`、`university`、`government`、`encyclopedia`、`publisher`、`journal`、`database`、`archive` |
| GitHub 同步 | 只同步工具代码、README、SKILL、计划文档、配置模板 |
| 本地测试 | `tests/` 保留本地，不推送 GitHub |

## 已完成计划

- 实现单文件 `extract`、`materialize`、`validate`、`serve`、`clean-stubs`。
- 翻译默认关闭，`translate_wiki.py` 仅显式配置后使用。
- `materialize` 不再自动生成占位页，缺失链接直接失败。
- 支持联网补充 `web_enrichments`，并渲染为 Quartz callout。
- 新增 `extract-dir`：批量抽取 `input/`，按 SHA256 复用未变化 blocks，输出 `source-manifest.json`。
- 新增 `merge-plans`：合并每篇文档的局部计划，合并 aliases/source_refs/outgoing_links/web_enrichments，并检查重复页面和断链。
- 新增 `build`：包装 `npx quartz build`。
- 扩展 schema：新增 `source_refs`、`aliases`，扩展学术来源类型。
- 更新 README、SKILL 和本计划文档，统一描述 input 批量摄入工作流。
- 添加本地单元测试覆盖批量抽取、计划合并、source refs、扩展 web source type 和 build 命令。

## 工作流

```powershell
python ingest_wiki.py extract-dir --input ".\input" --out ".\ingest-output"
```

Claude Code 按文档读取 `ingest-output/blocks/*.blocks.json`，生成局部计划到：

```text
ingest-output/plans/*.plan.json
```

合并局部计划：

```powershell
python ingest_wiki.py merge-plans ".\ingest-output\plans" --out ".\ingest-plan.json"
```

写入与验证：

```powershell
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --dry-run
python ingest_wiki.py materialize ".\ingest-plan.json" --wiki ".\wiki" --apply
python ingest_wiki.py validate --wiki ".\wiki"
python ingest_wiki.py build --wiki ".\wiki"
python ingest_wiki.py serve --wiki ".\wiki" --port 8888
```

## 下一步计划

1. 用当前 `input/` 生成私有 `ingest-output/`。
2. 按文档生成局部计划，重点处理讲解词路线、研究文献主题、跨文档实体/概念复用。
3. 合并为总 `ingest-plan.json` 后增量写入当前 `wiki/`。
4. 根据 validate/build 结果修复断链、锚点和来源字段。
5. 后续增加更细的局部计划生成辅助提示和 URL 可达性检查。

## GitHub 同步原则

可以同步：

- `llm_wiki_ingest/`
- `ingest_wiki.py`
- `translate_wiki.py`
- `README.md`
- `README.zh.md`
- `SKILL.md`
- `config.example.md`
- `requirements.txt`
- `docs/llm-wiki-ingest-plan.md`

不得同步：

- `input/`
- `ingest-output/`
- 原始 `.docx` / `.pdf`
- `*.blocks.json`
- 私有 `ingest-plan.json`
- 私有 `wiki/`
- Quartz `public/`
- 本地密钥配置 `config.md`
- `.claude/`
- `tests/`
