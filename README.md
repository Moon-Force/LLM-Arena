# LLM Arena · 多模型编程智能体竞技场

基于官方 **[OpenCode](https://www.npmjs.com/package/opencode-ai)** 的公平多模型编程 Agent 评测平台。

> **相同任务 · 相同工具 · 相同约束 —— 只换模型**（单一变量原则）

[![OpenCode](https://img.shields.io/badge/引擎-opencode--ai-orange)](https://www.npmjs.com/package/opencode-ai)
[![Stack](https://img.shields.io/badge/技术栈-Vue3%20%7C%20FastAPI%20%7C%20Docker-informational)](./llm-arena)
[![Repo](https://img.shields.io/badge/GitHub-Moon--Force%2FLLM--Arena-blue)](https://github.com/Moon-Force/LLM-Arena)

## 项目简介

LLM Arena 用于在**受控、可复现**的条件下比较不同大模型作为编程智能体的能力：

| 能力 | 说明 |
|------|------|
| 公平对战 | 冻结工具、系统提示、温度、步数、超时；仅模型与 API 凭证可不同 |
| 官方 Agent | 不使用自研 ReAct；运行时 = `opencode serve` + 官方 tools |
| 硬隔离 | 默认 Docker：每模型独立容器与 workspace |
| 自动判分 | 任务结束后在 workspace 内执行 **pytest**（fail→pass 风格） |
| 评测赛道 | algorithm / bugfix / feature / frontend 等 |
| 任务工坊 | 前端 `/tasks` 可创建、编辑自定义任务 |

**关键词：** LLM 评测 · 编程智能体 · OpenCode · 公平竞技场 · 多模型对比 · pytest · 排行榜 · SWE-bench 风格

## 快速开始

```bash
cd llm-arena

# —— 后端 ——
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
# source venv/bin/activate
pip install -r requirements.txt
python -m opencode.api.server

# —— 前端（另开终端）——
npm install
npm run dev
```

| 服务 | 地址 |
|------|------|
| 前端界面 | http://127.0.0.1:3000 |
| API 文档 | http://127.0.0.1:8000/docs |

更完整的配置、Docker、环境变量说明见：**[llm-arena/README.md](./llm-arena/README.md)**  
赛道设计说明见：**[评测赛道实施文档](./llm-arena/docs/eval-tracks-implementation.md)**

## 仓库结构

```text
LLM-Arena/
├── README.md                 # 本文件（中文总览）
└── llm-arena/                # 主应用
    ├── src/                  # Vue 3 前端
    ├── opencode/             # FastAPI + OpenCode 运行时
    ├── tasks/                # 评测任务（task.json + 测试）
    ├── docs/                 # 设计与实施文档
    ├── Dockerfile.opencode   # Agent 隔离镜像
    └── README.md             # 详细中文文档
```

## 使用流程（简要）

1. 在 **模型配置** 页填入各模型的 API Key / Base URL  
2. 在 **任务** 页选用内置题，或自行创建任务（脚手架 + pytest）  
3. 在 **竞技场** 选择赛道、≥2 个模型与同一任务，开始对战  
4. 实时查看 OpenCode 过程；结束后自动切预览，并以 pytest 通过率为准  
5. 在 **排行榜 / Agent 产出** 查看结果与生成文件  

## 判分原则

- **成功** = 该任务全部 pytest 通过（`passed == total`）  
- Agent 说「完成」或 run 状态 `success` **不等于** 题做对  
- 页面预览仅供查看，**裁判是测试**  

## 默认分支

远程默认分支为 **`master`**。开发与推送请基于 `master`：

```bash
git checkout master
git pull origin master
# … 开发 …
git push origin master
```

## 许可证

详见 `llm-arena` 目录内说明（MIT）。欢迎 Issue / PR。
