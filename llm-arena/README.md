# LLM Arena - OpenCode 多模型编程竞技场

> **Tags:** LLM benchmark · coding agent · OpenCode · fair evaluation · SWE-bench style · pytest · multi-model arena · agent leaderboard

基于**官方 [opencode-ai](https://www.npmjs.com/package/opencode-ai)** 的多模型编程能力评测平台。  
Agent 不自研：对战进程 = `opencode serve` + 官方内置 tools。

**仓库：** [github.com/Moon-Force/LLM-Arena](https://github.com/Moon-Force/LLM-Arena)

## 单一变量原则（公平评测）

对战中**仅允许**不同：

- `model_id` / `provider` / `version`
- `api_key` / `base_url`（接入凭证）

以下全部**冻结**（见 `GET /api/v1/constraints`）：

- 系统提示词与版本号、工具协议（官方 OpenCode tools）
- `temperature=0`、`max_tokens`、`max_steps`、`timeout`
- 同一 `opencode-ai` 版本与 agent（build）

多模型对战：

```http
POST /api/v1/arena
{
  "task_id": "bugfix-null-pointer",
  "parallel": true,
  "models": [
    { "model_id": "deepseek-v4-pro", "provider": "deepseek", "version": "deepseek-v4-pro" },
    { "model_id": "mimo-v2.5-pro", "provider": "mimo", "version": "mimo-v2.5-pro", "base_url": "https://api.xiaomimimo.com/v1" }
  ]
}
```

前端 Arena 页多选 ≥2 个模型即可发起公平对战。

### 模型怎么跑（只有一种方式）

1. API 为每个模型准备**独立 workspace**  
2. 默认用 **Docker 硬隔离** 启动官方 `opencode serve`（容器内只挂载该模型目录）  
3. HTTP 创建 session、发送任务；过程推送到前端  
4. 结束后在 workspace 上跑 **pytest** 评测，并销毁容器  

| 变量 | 默认 | 说明 |
|------|------|------|
| `OPENCODE_ISOLATION` | `auto` | `docker` 硬隔离 / `process` 进程级 / `auto` 有 Docker 则 docker |
| `OPENCODE_IMAGE` | `opencode-arena-agent:latest` | 隔离镜像（`Dockerfile.opencode`） |
| `OPENCODE_BIN` | 自动 | 仅 process 模式需要 |

```bash
# 预构建隔离镜像（首次对战也会自动 build）
docker build -f Dockerfile.opencode -t opencode-arena-agent:latest .
```

**硬隔离保证：** 每个 contestant 独立容器 + 仅绑定自己的 `.../model__runid/src`，看不到其它模型目录。

## 快速启动

### 方式一：仅启动前端（开发模式）

```bash
cd llm-arena
npm install
npm run dev
```

访问 http://127.0.0.1:3000（若端口被占用可改用 Vite 提示的端口）

### 方式二：Docker 部署 API + Redis

#### 1. 环境准备

确保已安装：
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env：可填默认 Key，也可只在前端模型配置里填
```

#### 3. 启动基础设施

```bash
docker compose up -d          # api + redis（Agent 为官方 opencode serve）
```

#### 4. 查看状态

```bash
docker compose ps
docker compose logs -f api
```

### 方式三：开发模式（前后端分离）

#### 启动后端

```bash
cd llm-arena

# 前端依赖（含官方 opencode-ai）
npm install

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动 API 服务器（官方 opencode-ai）
python -m opencode.api.server
```

后端默认运行在 http://localhost:8000

#### 启动前端

```bash
cd llm-arena
npm install
npm run dev
```

前端默认运行在 http://127.0.0.1:3000

## 环境变量配置

创建 `.env` 文件：

```env
# API Keys
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
DEEPSEEK_API_KEY=your_deepseek_key

# 可选：自定义 Base URL
# OPENAI_BASE_URL=https://your-proxy.com/v1

# 后端配置
OPENCODE_ENV=development
OPENCODE_MAX_STEPS=100
OPENCODE_TIMEOUT=300

# 数据库
DATABASE_URL=sqlite:///data/opencode.db

# Redis
REDIS_URL=redis://localhost:6379
```

## 常用命令

```bash
# 构建镜像
docker-compose build

# 重新构建并启动
docker-compose up -d --build

# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v

# 查看实时日志
docker-compose logs -f

# 进入容器调试
docker-compose exec api bash

# 运行测试
docker-compose exec api pytest
```

## 项目结构

```
llm-arena/
├── src/                    # Vue 3 前端
│   ├── components/         # 组件（含 OpenCodeTerminal）
│   ├── views/              # 页面
│   ├── stores/             # Pinia Store
│   └── i18n/               # 国际化 (en/zh)
├── opencode/               # Python 后端（编排 + 评测）
│   ├── core/
│   │   ├── opencode_runtime.py  # 官方 opencode serve 客户端
│   │   ├── arena_runner.py      # 多模型对战编排
│   │   ├── task_runner.py       # 任务 / workspace / pytest
│   │   ├── agent.py             # 结果类型（非自研循环）
│   │   └── fairness.py          # 冻结约束
│   └── api/server.py       # FastAPI
├── tasks/                  # 编程任务模板
├── node_modules/opencode-ai/  # 官方 OpenCode 二进制
├── docker-compose.yml      # API + Redis（可选）
├── Dockerfile              # API 服务镜像
└── requirements.txt
```

## 设计文档

| 文档 | 说明 |
|------|------|
| [docs/eval-tracks-implementation.md](./docs/eval-tracks-implementation.md) | 竞技场按评测内容分赛道（Track）的完整实施说明 |

## API 文档

启动后访问：http://localhost:8000/docs

### 主要端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/models` | 列出可用模型 |
| GET | `/api/v1/tasks` | 列出任务 |
| POST | `/api/v1/runs` | 开始竞技场运行 |
| GET | `/api/v1/runs/{id}` | 获取运行状态 |
| GET | `/api/v1/leaderboard` | 获取排行榜 |
| WS | `/ws/runs/{id}` | WebSocket 实时更新 |

## 模型配置

访问 http://127.0.0.1:3000/models 配置模型：

1. **内置模型**：Claude Opus、GPT-4o、Gemini Pro、DeepSeek V4 Pro
2. **自定义模型**：点击 "Add Model" 添加自己的模型
3. **启用/禁用**：点击开关控制模型是否参与评测
4. **API Key**：可选，为空则使用环境变量

## 开发指南

### 添加新任务

在 `tasks/` 目录下创建任务目录：

```
tasks/
└── my-task/
    ├── task.json          # 任务描述
    ├── src/               # 初始代码（或与 test_*.py 同级）
    └── tests/             # 测试用例（或 test_*.py）
```

### 前端能力任务（HTML）

已内置若干前端评测任务（参考 FrontendBench / 前端 coding-agent 常见题型）：

| ID | 类型 | 说明 |
|----|------|------|
| `feature-landing-hero` | feature | 落地页 Hero + 导航 + 特性卡片 |
| `bugfix-navbar-mobile` | bugfix | 移动端汉堡导航 / `menu-open` |
| `feature-todo-app` | feature | 可交互 Todo（增删完成） |
| `feature-pricing-toggle` | feature | 定价页月/年切换 |
| `bugfix-form-a11y` | bugfix | 表单可访问性与校验 |

生成结果为 `index.html` 等，可在前端 **Agent 产出** 页预览 HTML。

### 添加新模型提供商

在前端「模型配置」中添加 provider / base_url / api_key。  
官方 OpenCode 通过 `opencode_runtime.build_opencode_config` 注入 `provider` 与凭证；  
自定义 OpenAI 兼容接口填 `base_url` 即可。

## 许可证

MIT
