# LLM Wiki 文档摄入改造计划

## 当前目标

将 `llm-wiki-skill` 改造成“文档摄入优先、默认联网补充”的 LLM Wiki 工具。脚本负责解析、落盘、渲染和校验；Claude Code 负责根据抽取结果生成摄入计划、拆分页面、组织互链，并用权威来源补充必要背景。

首批本地验证材料是讲解词，但讲解词原文、抽取出的 blocks、私有 `ingest-plan.json` 及其派生 wiki 内容不进入 GitHub。

## 已完成的需求对齐

- 主目标：通用摄入管线 + 讲解词作为首个本地验证样例。
- Wiki 形态：使用 Quartz 构建 Markdown 到 HTML。
- 页面模型：路线页 + 知识图谱页。
- 内容语言：中文主文。
- 联网补充：默认开启，由 Claude Code 检索与写作；脚本不直接联网。
- 来源策略：优先博物馆、图书馆、高校、政府、出版社，百科仅作兜底。
- 查询边界：只使用实体名、书名、概念名，不使用讲解词原文片段作为搜索词。
- 输入格式：`DOCX / PDF / MD / TXT`。
- 实现形态：脚本 + skill 编排，后续再考虑完整 CLI。
- 职责划分：脚本解析和写入，Claude Code 写作、互链和联网补充。
- 人工确认：先 dry-run 和审摄入计划，再 apply。
- 链接质量：不再自动生成占位页，缺失 `outgoing_links` 目标直接失败。
- 概念粒度：中等偏密，首轮目标约 20-35 个概念页。
- Git 同步：功能分支推送，不直接推 `main`。
- 部署范围：首版不配置 GitHub Pages。

## 决策清单

| 决策 | 当前选择 |
| --- | --- |
| 页面模型 | 路线 + 知识图谱 |
| 实体分类 | 展品、典籍、人物、概念、地点 |
| 输入格式 | DOCX、PDF、MD、TXT |
| 翻译 | 默认关闭 |
| 中文源文档 | 默认生成中文主文 |
| 联网补充 | 默认开启，必须标注为“联网补充” |
| 联网执行者 | Claude Code 检索与写作，脚本不联网 |
| 来源类型 | `museum`、`library`、`university`、`government`、`encyclopedia`、`publisher` |
| 查询策略 | 仅使用实体名、书名、概念名 |
| 补充密度 | 中等：stop 页 0-2 条，实体/概念页约 1 条，不补首页 |
| HTML 生成 | Quartz build |
| manifest | 维护 `llm-wiki-manifest.json`，记录页面和 `web_sources` |
| 占位页 | 不自动生成；旧占位页通过 `clean-stubs` 显式清理 |
| 概念范围 | 版本学、工艺、分类体系、文献体裁、版本载体/形态 |
| 概念命名 | 优先使用拼音 slug，避免英文同义重复 |
| GitHub 同步 | 只同步工具代码、README、计划文档、配置模板 |
| 隐私边界 | 讲解词、blocks、私有计划和派生 wiki 内容不进入 GitHub |

## 已完成计划

- 新增摄入工具包 `llm_wiki_ingest`。
- 新增命令入口 `ingest_wiki.py`。
- 实现 `extract`：抽取 DOCX/PDF/MD/TXT 为标准 JSON 文本块。
- 实现 `materialize`：根据摄入计划写入 Quartz Markdown 页面和 manifest。
- 实现 `validate`：检查 frontmatter、wikilink 断链和 manifest 页面存在性。
- 改造 `materialize`：缺失链接目标直接失败，不再自动补占位页。
- 新增 `clean-stubs`：显式清理旧版本生成的占位页。
- 改造 `validate`：残留占位页视为校验错误。
- 新增联网补充 schema：根级 `web_enrichment` 和页面级 `web_enrichments`。
- 改造 `materialize`：按 `anchor_text` 插入 Quartz “联网补充” callout，并写入去重后的 `web_sources`。
- 改造 `validate`：检查 manifest 中 `web_sources` 字段完整性和 `source_type` 合法性。
- 将 `translate_wiki.py` 改为可选工具，默认关闭翻译，移除硬编码 API key 和个人路径。
- 更新 `config.example.md`，默认 `primary_engine: none`、`fallback_engine: none`、`bilingual_default: false`。
- 重写 `SKILL.md`，聚焦文档摄入、互链、占位页清理和联网补充流程。
- 重写中英文 README，其中中文 README 为主要使用文档。
- 添加本地单元测试覆盖抽取、slug、页面生成、链接校验、占位页清理、联网补充和翻译默认关闭。`tests/` 默认不推送 GitHub。

## 下一步计划

1. 使用讲解词在本地生成私有 `wiki/`，验证路线页、实体页和概念页结构。
2. 在私有 `ingest-plan.json` 中逐步补充联网增强内容，但不作为本次代码提交的一部分。
3. 根据首个样例继续完善概念页正文、跨页链接和来源选择标准。
4. 增强 PDF 支持；扫描版 PDF 需要单独 OCR 流程。
5. 为大型文档增加分页/分批摄入策略。
6. 增加可选 URL 可达性检查和更细的来源质量报告。
7. 后续再设计完整 CLI 工具和 GitHub Pages 部署流程。

## 测试与验收

自动化测试：

```powershell
python -m unittest discover -v
```

手动验收：

1. 使用讲解词执行 `extract`，输出本地私有 `*.blocks.json`。
2. 由 Claude Code 生成摄入计划，必要时加入带来源的 `web_enrichments`。
3. 执行 `materialize --dry-run` 检查页面数量、断链、联网补充锚点和来源字段。
4. 如旧 wiki 中存在占位页，执行 `clean-stubs --dry-run` 和 `clean-stubs --apply`。
5. 执行 `materialize --apply` 写入本地私有 `wiki/`。
6. 执行 `validate --wiki wiki`。
7. 在 Quartz 项目中执行 `npx quartz build`。
8. 执行 `git status --short`，确认讲解词、抽取结果、私有计划、私有 wiki 和 HTML 产物没有 staged。

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

- 原始讲解词 `.docx`
- 由讲解词抽取出的 `*.blocks.json`
- 私有 `ingest-plan.json`
- 由讲解词生成的 `wiki/` 内容
- Quartz `public/` HTML 产物
- 本地密钥配置 `config.md`
- `.claude/`
- `tests/`
