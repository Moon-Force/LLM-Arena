# LLM Arena - OpenCode 多模型编程竞技场

基于 OpenCode 的多模型编程能力评测平台，支持 Docker 容器化部署。

## 快速启动

### 方式一：仅启动前端（开发模式）

```bash
cd llm-arena
npm install
npm run dev
```

访问 http://localhost:5173

### 方式二：Docker 完整部署（推荐）

#### 1. 环境准备

确保已安装：
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥
```

#### 3. 启动服务

```bash
# 启动所有服务（API + Redis + 所有模型容器）
docker-compose up -d

# 或只启动 API 和 Redis
docker-compose up -d api redis
```

#### 4. 查看状态

```bash
# 查看运行中的容器
docker-compose ps

# 查看日志
docker-compose logs -f api

# 查看特定模型日志
docker-compose logs -f model-claude-opus
```

### 方式三：开发模式（前后端分离）

#### 启动后端

```bash
cd llm-arena

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动 API 服务器
python -m opencode.api.server
```

后端默认运行在 http://localhost:8000

#### 启动前端

```bash
cd llm-arena
npm install
npm run dev
```

前端默认运行在 http://localhost:5173

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
│   ├── components/         # 组件
│   ├── views/              # 页面
│   ├── stores/             # Pinia Store
│   ├── i18n/               # 国际化 (en/zh)
│   └── ...
├── opencode/               # Python 后端
│   ├── core/               # 核心模块
│   │   ├── agent.py        # Agent 循环
│   │   ├── tool_registry.py # 工具注册
│   │   ├── container_runner.py # Docker 容器管理
│   │   ├── model_client.py # LLM 客户端
│   │   ├── task_runner.py  # 任务执行
│   │   └── arena_runner.py # 竞技场编排
│   └── api/                # FastAPI 服务器
├── tasks/                  # 编程任务模板
├── docker-compose.yml      # Docker 编排
├── Dockerfile              # 主应用镜像
├── Dockerfile.model        # 模型运行器镜像
└── requirements.txt        # Python 依赖
```

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

访问 http://localhost:5173/models 配置模型：

1. **内置模型**：Claude Opus、GPT-4o、Gemini Pro、DeepSeek Chat
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
    ├── src/               # 初始代码
    └── tests/             # 测试用例
```

### 添加新模型提供商

在 `opencode/core/model_client.py` 中继承 `BaseModelClient`：

```python
class MyClient(BaseModelClient):
    async def chat(self, messages, **kwargs):
        # 实现聊天接口
        pass
```

## 许可证

MIT
