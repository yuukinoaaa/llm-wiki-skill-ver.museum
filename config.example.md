---
configured: true
---

# LLM Wiki 配置文件模板

复制此文件为 `config.md` 后按本地环境修改。`config.md` 已被 `.gitignore` 排除，不会提交到 GitHub。

## Source Directories

本地源文档目录。源文档只读，摄入流程不会修改这些文件。

- C:/path/to/your/source-documents

## Wiki Directory

Quartz Wiki 项目目录。示例：

```text
C:/path/to/your/wiki
```

## GitHub Pages

首版默认不配置 GitHub Pages。需要部署时再填写：

```text
https://yourname.github.io/your-wiki
```

## Translation Settings

翻译默认关闭。中文文档摄入后默认生成中文主文，不自动生成双语内容。

```yaml
primary_engine: none
fallback_engine: none
bilingual_default: false
```

如需手动翻译已有英文页面，可显式启用 `translate_wiki.py`：

```powershell
$env:LLM_WIKI_TRANSLATION_ENGINE = "zhipu"
$env:ZHIPU_API_KEY = "your-local-api-key"
python translate_wiki.py --content-dir C:/path/to/wiki/content --engine zhipu
```
