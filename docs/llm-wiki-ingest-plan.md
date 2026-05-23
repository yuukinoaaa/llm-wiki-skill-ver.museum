# LLM Wiki 文档摄入改造计划

## 当前目标

将 `llm-wiki-skill` 改造成“文档摄入优先”的 LLM Wiki 工具。脚本负责解析、落盘和校验，Claude Code 负责根据抽取结果生成摄入计划、拆分页面、组织互链。

首批本地验证材料是讲解词，但讲解词原文及其派生 wiki 内容不进入 GitHub。

## 已完成的需求对齐

- 主目标：通用摄入管线 + 讲解词作为首个本地验证样例。
- Wiki 形态：使用 Quartz 构建 Markdown 到 HTML。
- 页面模型：路线页 + 知识图谱页。
- 内容语言：中文主文。
- 内容边界：首版严格基于源文档，不联网补充。
- 输入格式：`DOCX / PDF / MD / TXT`。
- 实现形态：脚本 + skill 编排，后续再考虑完整 CLI。
- 职责划分：脚本解析和写入，Claude Code 写作和互链。
- 人工确认：先 dry-run 和审摄入计划，再 apply。
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
| HTML 生成 | Quartz build |
| manifest | 维护 `llm-wiki-manifest.json` |
| GitHub 同步 | 只同步工具代码、测试、README、计划文档、配置模板 |
| 隐私边界 | 讲解词和派生 wiki 内容不进入 GitHub |

## 已完成计划

- 新增摄入工具包 `llm_wiki_ingest`。
- 新增命令入口 `ingest_wiki.py`。
- 实现 `extract`：抽取 DOCX/PDF/MD/TXT 为标准 JSON 文本块。
- 实现 `materialize`：根据摄入计划写入 Quartz Markdown 页面和 manifest。
- 实现 `validate`：检查 frontmatter、wikilink 断链和 manifest 页面存在性。
- 将 `translate_wiki.py` 改为可选工具，默认关闭翻译，移除硬编码 API key 和个人路径。
- 更新 `config.example.md`，默认 `primary_engine: none`、`fallback_engine: none`、`bilingual_default: false`。
- 重写 `SKILL.md`，聚焦文档摄入流程。
- 重写中英文 README，其中中文 README 为主要使用文档。
- 添加单元测试覆盖抽取、slug、页面生成、链接校验和翻译默认关闭。

## 下一步计划

1. 使用讲解词在本地生成私有 `wiki/`，验证路线页和实体页结构。
2. 根据首个样例补充更细的摄入计划模板和提示词片段。
3. 增强 PDF 支持；扫描版 PDF 需要单独 OCR 流程。
4. 为大型文档增加分页/分批摄入策略。
5. 在用户明确授权后，增加联网补充和引用校验。
6. 后续再设计完整 CLI 工具和 GitHub Pages 部署流程。

## 测试与验收

自动化测试：

```powershell
python -m unittest discover -v
```

手动验收：

1. 使用讲解词执行 `extract`，输出本地私有 `*.blocks.json`。
2. 由 Claude Code 生成摄入计划。
3. 执行 `materialize --dry-run` 检查页面数量。
4. 执行 `materialize --apply` 写入本地私有 `wiki/`。
5. 执行 `validate --wiki wiki`。
6. 在 Quartz 项目中执行 `npx quartz build`。
7. 执行 `git status --short`，确认讲解词、抽取结果、私有 wiki 和 HTML 产物没有 staged。

## GitHub 同步原则

可以同步：

- `llm_wiki_ingest/`
- `ingest_wiki.py`
- `translate_wiki.py`
- `tests/`
- `README.md`
- `README.zh.md`
- `SKILL.md`
- `config.example.md`
- `requirements.txt`
- `docs/llm-wiki-ingest-plan.md`

不得同步：

- 原始讲解词 `.docx`
- 由讲解词抽取出的 `*.blocks.json`
- 由讲解词生成的 `wiki/` 内容
- Quartz `public/` HTML 产物
- 本地密钥配置 `config.md`
