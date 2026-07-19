# 竞技场评测内容分区 — 实施文档

> 状态：设计稿（待开发）  
> 范围：按 LLM 评测内容拆分赛道（Track）、任务池、计分与排行榜  
> 引擎：官方 OpenCode（`opencode-ai`）+ Docker 硬隔离  
> 日期：2026-07-19

---

## 1. 背景与目标

### 1.1 现状

LLM Arena 已具备：

- 官方 OpenCode Agent（全套 tools，Docker 每模型独立 workspace）
- 公平对战：单一变量原则（仅 model / provider / version / api_key / base_url 可变）
- 任务目录：`tasks/python/*`、`tasks/html/*`（bugfix / feature）
- 自动评测：workspace 内 `pytest`
- 前端：Arena 对战、Agent 产出、排行榜

任务目前主要靠 `language` + `type` + `difficulty` 区分，**缺少明确的评测赛道（Track）**，排行榜也无法按评测内容拆分。

### 1.2 目标

1. 引入 **评测赛道（Track）**，对应业界不同 LLM 编程评测形态  
2. 任务、对战、排行榜均按赛道组织  
3. 同一套 OpenCode 引擎与冻结约束，**仅任务池与（可选）工具策略可按赛道差异化**  
4. 分阶段落地，先兼容现有任务，再扩展题库  

### 1.3 非目标（本期不做）

- 完整复刻 SWE-bench 官方数据与评测 harness  
- 人类双盲 Elo（可作为后续 Frontend 美学补充）  
- 替换官方 OpenCode 为其它 Agent 框架  

---

## 2. 业界评测方式调研摘要

| 类型 | 代表基准 | 测什么 | 判分 |
|------|----------|--------|------|
| 函数 / 算法 | HumanEval, MBPP, LiveCodeBench | 写函数、竞赛题 | 单测 pass@k |
| 仓库级修 Bug | SWE-bench / Verified / Live | 真实 issue + 多文件 | 官方测试 |
| 多语言代码 | MultiPL-E, SWE-bench Multilingual | 跨语言生成与修复 | 各语言测试 |
| 前端 / UI | FrontendBench, WebDev Arena | 页面、交互、a11y | DOM 断言 / 人类偏好 |
| 工具 / Agent | τ-bench, ToolBench, BrowserArena | 多步工具、浏览器 | 任务完成率 |
| 安全 | CyberSecEval 等 | 漏洞代码、注入、越权 | 安全规则 + 动静态分析 |
| 对话偏好 | LMSYS Chatbot Arena | 通用回答质量 | 人类 Elo |

**对本项目的启示：**

- 自动可执行 + 同工具冻结 → 适合 **Coding / Agent 分赛道**，而非纯 Chat 偏好  
- 任务需带 **赛道标签**；榜按赛道拆，避免「算法强、前端弱」混成一个总分误导  
- 先做与现有题库重合的赛道，再补算法 / 工具 / 安全  

---

## 3. 赛道定义（Track）

### 3.1 赛道一览

| Track ID | 名称 | 对应业界 | 主指标 | 辅指标 | 工具策略建议 |
|----------|------|----------|--------|--------|--------------|
| `algorithm` | 算法与函数 | HumanEval / LiveCodeBench | pass@1 | tokens、耗时 | 可关 websearch（防泄题） |
| `bugfix` | Bug 修复 | 迷你 SWE | 测试通过率 | 步数、回归 | 全工具 |
| `feature` | 功能实现 | 工程 feature 题 | 功能测通过率 | 隐藏测例 | 全工具 |
| `frontend` | 前端 / UI | FrontendBench | DOM/行为通过率 | 可选美观分 | 全工具 |
| `tooluse` | Agent 工具 | τ-bench 轻量 | 任务完成 + 关键 tool | 多余调用惩罚 | 强调 bash/webfetch/websearch |
| `safety` | 安全（可选） | CyberSecEval 轻量 | 安全测通过 / 拒绝率 | 误拒 | 可限制危险 bash |

### 3.2 与现有任务映射

| 现有路径 / type | 建议 track |
|-----------------|------------|
| `tasks/python/*/bugfix-*` | `bugfix` |
| `tasks/python/*/feature-*` | `feature` |
| `tasks/html/*/bugfix-*` | `frontend`（或 `bugfix`，优先 frontend） |
| `tasks/html/*/feature-*` | `frontend` |
| 新建 `tasks/python/algo-*` | `algorithm` |
| 新建 `tasks/*/tool-*` | `tooluse` |
| 新建 `tasks/*/safety-*` | `safety` |

**兼容规则：** 若 `task.json` 无 `track` 字段，后端按下列启发式推断：

```
if language in (html, css, js, typescript) → frontend
elif type == bugfix → bugfix
elif type == feature → feature
else → feature
```

---

## 4. 数据模型

### 4.1 `task.json` 扩展

```json
{
  "id": "feature-landing-hero",
  "name": "Landing Hero Page",
  "description": "...",
  "language": "html",
  "type": "feature",
  "track": "frontend",
  "difficulty": "easy",
  "test_cases": 8,
  "expected_files": ["index.html"],
  "scoring": {
    "primary": "pass_rate",
    "weights": {
      "pass_rate": 0.7,
      "hidden_pass_rate": 0.3
    }
  },
  "tools_policy": "full",
  "hidden_tests": [],
  "tags": ["ui", "marketing", "static"]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `track` | string | 赛道 ID，见 §3.1 |
| `scoring` | object | 可选，覆盖赛道默认计分 |
| `tools_policy` | string | `full` \| `no_web` \| `readonly`（Phase 2） |
| `tags` | string[] | 检索 / 筛选 |

### 4.2 赛道元数据（后端常量或 `config/tracks.json`）

```json
{
  "tracks": [
    {
      "id": "frontend",
      "name": { "zh": "前端 / UI", "en": "Frontend / UI" },
      "description": { "zh": "页面结构、交互与可访问性", "en": "Layout, interaction, a11y" },
      "icon": "layout",
      "order": 4,
      "enabled": true,
      "default_tools_policy": "full",
      "metrics": ["pass_rate", "hidden_pass_rate", "avg_tokens", "avg_duration"]
    }
  ]
}
```

### 4.3 Run / Arena 记录扩展

| 字段 | 位置 | 说明 |
|------|------|------|
| `track` | run + arena | 本场使用的赛道 |
| `task_id` | 已有 | 不变 |
| `metrics` | run | 规范化指标快照（便于排行榜） |

---

## 5. 计分方案

### 5.1 单次 run 指标

```text
pass_rate        = passed / total          （公开测）
hidden_pass_rate = hidden_passed / hidden_total
duration         = 秒
tokens_used      = OpenCode 累计
steps            = agent 轮次数
status           = completed | failed
```

### 5.2 赛道内模型综合分（Leaderboard）

默认（可配置）：

```text
track_score =
  0.50 * avg(hidden_pass_rate or pass_rate)
+ 0.30 * avg(pass_rate)
+ 0.20 * stability   # completed_runs / runs
```

- **不**用「跨赛道硬平均」当默认总榜；总榜若存在，需标明「全赛道加权」并单独文档化  
- Phase 3 可为 `frontend` 增加可选人工美观分（0–1），权重默认 0  

### 5.3 tooluse 赛道附加规则（Phase 2）

- 任务描述中声明 **必须** 调用的 tools（如 `webfetch`）  
- 从 `agent_steps` / messages 解析是否出现对应 tool  
- `tool_compliance` ∈ {0, 1}，进入 track_score 权重（如 0.2）  

---

## 6. API 变更

### 6.1 `GET /api/v1/tracks`

```json
{
  "tracks": [
    {
      "id": "frontend",
      "name": { "zh": "前端 / UI", "en": "Frontend / UI" },
      "enabled": true,
      "task_count": 8,
      "order": 4
    }
  ]
}
```

### 6.2 `GET /api/v1/tasks`

- 支持查询：`?track=frontend&difficulty=easy`  
- 响应每项含 `track`（推断或显式）  

### 6.3 `POST /api/v1/arena`

```json
{
  "task_id": "feature-landing-hero",
  "track": "frontend",
  "parallel": true,
  "models": [ ... ]
}
```

- 若传 `track`，校验 `task.track == track`（或推断结果一致）  
- 不传则从 task 推断  

### 6.4 `GET /api/v1/leaderboard`

- 查询：`?type=overall&track=frontend`  
- `track` 缺省时：返回全量 run（兼容旧前端），或返回「需指定 track」——**推荐强制 track 或提供 `track=all` 显式全量**  

---

## 7. 前端变更

### 7.1 Arena 页

```
[ 赛道选择：算法 | Bug修复 | 功能 | 前端 | 工具 | 安全 ]
        ↓
[ 该赛道下的任务列表 ]
        ↓
[ 模型多选 ≥2 ] + 并行
        ↓
[ 开始公平对战 ]
```

- 切换赛道时清空当前 task 选择  
- 约束卡片旁展示：`track` + 工具策略摘要  

### 7.2 排行榜页

- 顶部 Track tabs  
- 表头指标可按赛道略调（Phase 2）  

### 7.3 i18n

- `tracks.*.name` / `description`  
- Arena：`selectTrack`、`trackEmpty`  

### 7.4 类型

```ts
export type EvalTrack =
  | 'algorithm'
  | 'bugfix'
  | 'feature'
  | 'frontend'
  | 'tooluse'
  | 'safety'

export interface Task {
  id: string
  name: string
  // ...
  track: EvalTrack
  tools_policy?: 'full' | 'no_web' | 'readonly'
}
```

---

## 8. 后端变更清单

| 模块 | 变更 |
|------|------|
| `opencode/core/task_runner.py` | `Task` 增加 `track`；加载 / 推断 |
| `opencode/core/tracks.py`（新建） | 赛道元数据、推断、校验 |
| `opencode/core/fairness.py` | 可选：按 `tools_policy` 微调 permission（Phase 2） |
| `opencode/core/opencode_runtime.py` | 接收 tools_policy → permission_map 变体 |
| `opencode/api/server.py` | `/tracks`、tasks/arena/leaderboard 过滤 |
| `opencode/core/run_store.py` | run 存 `track` |
| `tasks/**/task.json` | 补 `track` 字段 |

---

## 9. 目录与任务库演进

### 9.1 推荐目录（渐进，不必立刻搬家）

```text
tasks/
  algorithm/
  bugfix/
  feature/
  frontend/          # 可由现有 html/* 迁移或符号映射
  tooluse/
  safety/
```

**Phase 1 可不迁目录**：仅 `task.json` 写 `track`，物理路径仍 `html/`、`python/`。

### 9.2 每赛道最低题量目标

| Phase | 每赛道题量 | 说明 |
|-------|------------|------|
| P1 | 沿用现有 + 打标 | frontend ≥6，bugfix/feature ≥2 |
| P2 | 每赛道 ≥5 | 补 algorithm、tooluse |
| P3 | 每赛道 ≥10 + 难度分层 | 含轻量多文件 SWE |

---

## 10. 实施阶段

### Phase 1 — 赛道骨架（约 1–2 天）

- [ ] 新增 `opencode/core/tracks.py`  
- [ ] `Task` / `task.json` 支持 `track` + 启发式推断  
- [ ] 现有全部 `task.json` 补 `track`  
- [ ] `GET /api/v1/tracks`、`GET /tasks?track=`  
- [ ] Arena UI：赛道选择 → 过滤任务  
- [ ] Leaderboard：`?track=` 过滤  
- [ ] i18n  

**验收：** 选 frontend 只看到 HTML 任务；排行榜按赛道只统计该赛道 runs。

### Phase 2 — 策略与题库（约 3–5 天）

- [ ] `tools_policy`：`no_web` 用于 algorithm  
- [ ] tooluse 示例任务 2–3 个（强制 webfetch 或 bash 流水线）  
- [ ] algorithm 示例任务 3–5 个（纯 pytest 函数题）  
- [ ] run 规范化 `metrics` 写入 store  
- [ ] 赛道默认计分权重可配置  

**验收：** algorithm 对战日志中无 websearch；tooluse 任务可检测关键 tool。

### Phase 3 — 增强（按需）

- [ ] 轻量多文件 bugfix（迷你 SWE）  
- [ ] 隐藏测例统一规范  
- [ ] Frontend 可选人类美观分  
- [ ] 导出赛道报告 JSON/CSV  
- [ ] 持续换题（Live 风格）流程文档  

---

## 11. 公平性约束（不变）

跨赛道仍遵守：

| 允许不同 | 必须相同（冻结） |
|----------|------------------|
| model_id / provider / version | OpenCode 版本与 agent=build |
| api_key / base_url | 同赛道 tools_policy |
| （赛道本身） | temperature、max_steps、timeout、system 骨架 |

**注意：** 不同赛道之间 **不要** 直接比 `track_score` 绝对值；对外展示始终带赛道标签。

---

## 12. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 旧前端不传 track | 后端从 task 推断，兼容 |
| 题量不均导致榜不稳定 | UI 显示 `n=` 样本数；题少赛道标 beta |
| websearch 泄题（算法） | algorithm 默认 `no_web` |
| Docker 镜像旧导致 tool 不一致 | 文档要求重建 `opencode-arena-agent` |
| 计分公式争议 | 权重配置化 + 文档写死默认值 |

---

## 13. 参考链接

- [SWE-bench](https://www.swebench.com)  
- [LiveCodeBench](https://livecodebench.github.io)  
- [OpenCode Tools](https://opencode.ai/docs/tools)  
- [LMSYS Chatbot Arena](https://lmarena.ai)（偏好对战方法论参考）  
- 本仓库：`README.md`、`opencode/core/fairness.py`、`opencode/core/opencode_tools.py`  

---

## 14. 决策记录（实施前确认）

| # | 问题 | 建议默认 | 状态 |
|---|------|----------|------|
| D1 | Phase 1 启用哪些赛道？ | bugfix, feature, frontend（现有题） | **已实施**；另 **algorithm 已启用**（hard 题库） |
| D2 | 排行榜是否允许 track=all？ | 允许，UI 含 All + 各赛道 | **已实施** |
| D3 | algorithm 是否默认禁网？ | 元数据 `default_tools_policy=no_web`；prompt 禁 web 搜题 | **部分实施**（硬禁 tools 仍可后续加） |
| D4 | 是否迁移 tasks 物理目录？ | Phase 1 不迁，只打标 | **已实施** |

---

## 15. 下一步

确认 §14 决策后，按 **Phase 1** 开工：

1. `tracks.py` + 任务打标  
2. API 过滤  
3. Arena / Leaderboard UI  

---

## 16. Phase 1 默认决策（可执行草案）

在未另行确认前，实施采用以下默认值（对应 §14）：

| # | 决策 | 采用值 |
|---|------|--------|
| D1 | 启用赛道 | `algorithm`、`bugfix`、`feature`、`frontend` 为 **enabled**；`tooluse` / `safety` 为 **beta 占位** |
| D2 | 排行榜 | 支持 `track=all`；UI 默认选 **最近一次对战的 track**，否则 `frontend` |
| D3 | algorithm 禁网 | track 元数据 + prompt 规则；runtime 硬禁 tools 可选后续 |
| D4 | 物理目录 | **不迁移**；只改 `task.json` + 推断逻辑 |

---

## 17. 文件级改造清单（Phase 1）

### 17.1 新建

| 路径 | 职责 |
|------|------|
| `opencode/core/tracks.py` | 赛道常量、元数据、`infer_track()`、`validate_track()`、`list_tracks()` |
| `config/tracks.json`（可选） | 若希望可配置化；Phase 1 可先写死在 `tracks.py` |
| `docs/eval-tracks-implementation.md` | 本文档 |

### 17.2 修改（后端）

| 路径 | 改动要点 |
|------|----------|
| `opencode/core/task_runner.py` | `Task` 增加 `track: str`；`_load_tasks` 读 `track` 或推断；`list_tasks(..., track=)` |
| `opencode/core/run_store.py` | `StoredRun` / `StoredArena` 增加 `track`；`to_public_run` 输出 `track` |
| `opencode/core/arena_runner.py` | `ArenaConfig` 可选 `track`；创建 run 时写入 store |
| `opencode/api/server.py` | `GET /tracks`；`list_tasks` 加 `track`；`start_arena` 校验/落库；`leaderboard` 按 track 过滤 |
| `opencode/core/fairness.py` | fingerprint **暂不**因 track 变化（工具仍全局 full）；Phase 2 再纳入 tools_policy |

### 17.3 修改（前端）

| 路径 | 改动要点 |
|------|----------|
| `src/types/index.ts` | `EvalTrack`、`Task.track` |
| `src/utils/api.ts` | `getTracks()`；`getTasks({ track })`；`getLeaderboard(type, track)` |
| `src/stores/arena.ts` | `tracks` state；`fetchTracks`；`fetchTasks` 带 track；normalize 含 track |
| `src/views/ArenaView.vue` | 赛道选择 UI → 过滤任务 |
| `src/views/LeaderboardView.vue` | 赛道 tabs |
| `src/i18n/locales/zh.json` / `en.json` | 赛道文案 |

### 17.4 修改（任务数据）

为每个现有 `task.json` 增加 `"track": "..."`，见 §18。

---

## 18. 现有任务打标表（Phase 1 必做）

| 任务 ID | 路径 | track |
|---------|------|-------|
| `bugfix-null-pointer` | `tasks/python/bugfix-null-pointer/` | `bugfix` |
| `feature-rate-limiter` | `tasks/python/feature-rate-limiter/` | `feature` |
| `feature-landing-hero` | `tasks/html/feature-landing-hero/` | `frontend` |
| `feature-todo-app` | `tasks/html/feature-todo-app/` | `frontend` |
| `bugfix-form-a11y` | `tasks/html/bugfix-form-a11y/` | `frontend` |
| `bugfix-navbar-mobile` | `tasks/html/bugfix-navbar-mobile/` | `frontend` |
| `feature-pricing-toggle` | `tasks/html/feature-pricing-toggle/` | `frontend` |
| `feature-saas-landing-pro` | `tasks/html/feature-saas-landing-pro/` | `frontend` |
| `feature-admin-users-table` | `tasks/html/feature-admin-users-table/` | `frontend` |
| `feature-kanban-board` | `tasks/html/feature-kanban-board/` | `frontend` |

每个文件最小 diff 示例：

```json
{
  "id": "feature-landing-hero",
  "track": "frontend",
  "...": "其余字段保持不变"
}
```

---

## 19. `tracks.py` 规格（伪代码级）

```python
# opencode/core/tracks.py

TRACK_IDS = (
    "algorithm", "bugfix", "feature",
    "frontend", "tooluse", "safety",
)

TRACK_META = {
    "bugfix": {
        "id": "bugfix",
        "order": 2,
        "enabled": True,
        "name": {"zh": "Bug 修复", "en": "Bugfix"},
        "description": {
            "zh": "在已有代码中定位并修复缺陷，以测试通过为准。",
            "en": "Locate and fix defects; scored by tests.",
        },
        "default_tools_policy": "full",
        "beta": False,
    },
    "feature": { "...": "enabled True, order 3" },
    "frontend": { "...": "enabled True, order 4" },
    "algorithm": { "...": "enabled False, beta True, order 1, no_web" },
    "tooluse": { "...": "enabled False, beta True, order 5" },
    "safety": { "...": "enabled False, beta True, order 6" },
}

def infer_track(language: str, type_: str, explicit: str | None = None) -> str:
    if explicit and explicit in TRACK_IDS:
        return explicit
    lang = (language or "").lower()
    typ = (type_ or "").lower()
    if lang in ("html", "css", "javascript", "typescript", "js", "ts"):
        return "frontend"
    if typ == "bugfix":
        return "bugfix"
    if typ == "feature":
        return "feature"
    return "feature"

def list_public_tracks(task_counts: dict[str, int] | None = None) -> list[dict]:
    """Return tracks for GET /api/v1/tracks (include disabled as beta)."""
    ...
```

### 19.1 Task 加载

```python
# task_runner._load_tasks 内
track = infer_track(
    task_data.get("language", ""),
    task_data.get("type", ""),
    task_data.get("track"),
)
task = Task(..., track=track)
```

### 19.2 list_tasks 过滤

```python
def list_tasks(self, language=None, difficulty=None, track=None):
    tasks = list(self.tasks.values())
    if track and track != "all":
        tasks = [t for t in tasks if t.track == track]
    ...
```

---

## 20. API 契约（完整）

### 20.1 `GET /api/v1/tracks`

**Response 200**

```json
{
  "tracks": [
    {
      "id": "frontend",
      "order": 4,
      "enabled": true,
      "beta": false,
      "name": { "zh": "前端 / UI", "en": "Frontend / UI" },
      "description": { "zh": "...", "en": "..." },
      "task_count": 8,
      "default_tools_policy": "full",
      "metrics": ["pass_rate", "hidden_pass_rate", "avg_tokens", "avg_duration", "stability"]
    }
  ]
}
```

### 20.2 `GET /api/v1/tasks`

**Query**

| 参数 | 类型 | 说明 |
|------|------|------|
| `track` | string | 赛道 ID 或 `all` |
| `language` | string | 已有 |
| `difficulty` | string | 已有 |

**Response item 增加**

```json
{
  "id": "feature-landing-hero",
  "track": "frontend",
  "name": "Landing Hero Page",
  "language": "html",
  "type": "feature",
  "difficulty": "easy",
  "test_cases": 8,
  "testCases": 8
}
```

（同时输出 snake_case 与 camelCase 的 `test_cases` / `testCases` 以兼容前端。）

### 20.3 `POST /api/v1/arena`

**Body 增加可选字段**

```json
{
  "task_id": "feature-landing-hero",
  "track": "frontend",
  "parallel": true,
  "models": [
    {
      "model_id": "deepseek-v4-pro",
      "provider": "deepseek",
      "version": "deepseek-v4-pro",
      "api_key": "...",
      "base_url": null
    }
  ]
}
```

**校验**

1. `task_id` 必须存在  
2. 解析 `task.track`  
3. 若 body 含 `track` 且 `track != "all"` 且 `track != task.track` → **400**  
   `detail: "Task feature-landing-hero belongs to track=frontend, not algorithm"`  
4. `StoredArena.track` / 各 `StoredRun.track` = `task.track`  

**Response 增加**

```json
{
  "arena_id": "arena-xxx",
  "track": "frontend",
  "task_id": "feature-landing-hero",
  "status": "running",
  "live": true,
  "runs": [ ... ]
}
```

### 20.4 `GET /api/v1/leaderboard`

**Query**

| 参数 | 默认 | 说明 |
|------|------|------|
| `type` | `overall` | 已有计分变体 |
| `track` | `all` | 赛道过滤 |

**逻辑**

```
runs = STORE.list_runs(status="completed")
if track and track != "all":
    runs = [r for r in runs if getattr(r, "track", None) == track]
# 再按 model 聚合 pass_rate / tokens / duration / stability
```

**Response item 增加**

```json
{
  "modelId": "deepseek-v4-pro",
  "track": "frontend",
  "runs": 12,
  "completedRuns": 11,
  "passRate": 72.5,
  "overallScore": 68.1,
  "sampleNote": "n=11"
}
```

### 20.5 `GET /api/v1/runs` / `GET /api/v1/runs/{id}`

- `to_public_run` 增加 `track`、`trackId`（同值，兼容命名）  

---

## 21. 前端交互规格

### 21.1 Arena 布局（文案流）

```
┌─────────────────────────────────────────────────────────────┐
│  赛道  [Bug修复] [功能实现] [前端/UI]  (algorithm 灰显 beta)   │
├──────────────┬──────────────────────────────────────────────┤
│ 模型多选     │  任务列表（仅当前赛道）                          │
│ ≥2           │  难度 / 语言标签                               │
│ 并行 ☑       │                                              │
│ [开始对战]   │  对战板 OpenCode 终端 …                        │
└──────────────┴──────────────────────────────────────────────┘
```

### 21.2 状态

| 状态 | 行为 |
|------|------|
| `selectedTrack` | 默认：`frontend`（题最多）或第一个 enabled |
| 切换 track | `selectedTask = null`；`fetchTasks({ track })` |
| 无任务 | 显示 `trackEmpty`，禁用开始按钮 |
| 开始对战 | `startFairArena` body 带 `track: selectedTrack` |

### 21.3 Leaderboard

```
[ All | Bugfix | Feature | Frontend | …beta ]
表格：Model | Runs(n) | Pass% | Hidden% | Tokens | Duration | Score
```

- `All` → `track=all`  
- 切换 tab 重新 `fetchLeaderboard`  

### 21.4 i18n 键（建议）

```json
{
  "tracks": {
    "label": "评测赛道",
    "all": "全部",
    "empty": "该赛道暂无任务",
    "beta": "即将推出",
    "bugfix": "Bug 修复",
    "feature": "功能实现",
    "frontend": "前端 / UI",
    "algorithm": "算法与函数",
    "tooluse": "Agent 工具",
    "safety": "安全"
  },
  "arena": {
    "selectTrack": "选择评测赛道",
    "trackHint": "不同赛道使用不同任务池；工具与冻结约束在同赛道内一致。"
  },
  "leaderboard": {
    "byTrack": "按赛道",
    "samples": "样本数"
  }
}
```

---

## 22. 计分实现细节

### 22.1 单 run 归一化 metrics

在 `finish_run` / arena 汇总时写入（可选字段，便于后续）：

```python
def compute_run_metrics(test_results: dict, tokens: int | None, duration: float | None) -> dict:
    total = int(test_results.get("total") or 0)
    passed = int(test_results.get("passed") or 0)
    ht = int(test_results.get("hidden_total") or test_results.get("hiddenTotal") or 0)
    hp = int(test_results.get("hidden_passed") or test_results.get("hiddenPassed") or 0)
    return {
        "pass_rate": (passed / total * 100.0) if total else None,
        "hidden_pass_rate": (hp / ht * 100.0) if ht else None,
        "tokens": tokens,
        "duration": duration,
        "passed": passed,
        "total": total,
    }
```

### 22.2 排行榜聚合（与现 store 逻辑对齐）

沿用 `src/stores/arena.ts` / `server.py` 现有 overall 公式，但 **输入 runs 先按 track 过滤**：

```text
overallScore =
  0.5 * (hiddenPassRate || passRate)
+ 0.3 * passRate
+ 0.2 * stability
```

`stability = completedRuns / runs * 100`

### 22.3 样本数展示

- `completedRuns < 3`：UI 标记「样本较少」  
- beta 赛道：tab 上显示 `beta` 徽章  

---

## 23. tools_policy（Phase 2 详设）

### 23.1 策略枚举

| policy | 效果 |
|--------|------|
| `full` | 与当前 `permission_map()` 一致（question deny） |
| `no_web` | `webfetch=deny`, `websearch=deny`；其余 full |
| `readonly` | `write/edit/bash=deny` 或 bash 仅允许 pytest（慎用，Phase 3） |

### 23.2 接入点

```python
# opencode_runtime.build_opencode_config(..., tools_policy="full")
perms = permission_map()
if tools_policy == "no_web":
    perms["webfetch"] = "deny"
    perms["websearch"] = "deny"
```

Docker / process 启动时同样应用。  
**赛道默认：** `algorithm → no_web`，其余 `full`。  
任务级 `tools_policy` 覆盖赛道默认。

### 23.3 公平性

同一场 arena 内所有模型必须同一 `tools_policy`（来自 task/track，禁止 per-model 覆盖）。

---

## 24. 新任务模板

### 24.1 algorithm 示例骨架

```text
tasks/python/algo-two-sum/
  task.json
  solution.py      # 空函数或 NotImplemented
  test_two_sum.py
```

`task.json`：

```json
{
  "id": "algo-two-sum",
  "name": "Two Sum",
  "track": "algorithm",
  "language": "python",
  "type": "feature",
  "difficulty": "easy",
  "tools_policy": "no_web",
  "expected_files": ["solution.py"],
  "test_cases": 5,
  "description": "Implement two_sum(nums, target) in solution.py. ..."
}
```

### 24.2 tooluse 示例骨架

```text
tasks/python/tool-fetch-and-parse/
  task.json
  test_fetch_task.py
```

描述中要求：使用 `webfetch` 或 `bash`+`curl` 获取给定 URL 的 JSON，写入 `out.json`，字段满足断言。  
计分 Phase 2：pytest + 可选 tool 合规检查。

### 24.3 轻量 SWE（Phase 3）

```text
tasks/python/swe-mini-login-bug/
  task.json
  src/
    app.py
    auth.py
  tests/
    test_login.py
  ISSUE.md
```

Agent 在多文件树中修复；测试只挂在 `tests/`。

---

## 25. 时序（一场对战）

```text
User                Frontend              API                 OpenCode×N
 |--选 track------->|                      |                     |
 |--选 task/models->|                      |                     |
 |--开始----------->|--POST /arena-------->|                     |
 |                  |                      |--create runs(track) |
 |                  |                      |--background-------->|
 |                  |                      |  per model:         |
 |                  |                      |   workspace+docker  |
 |                  |                      |   opencode serve    |
 |                  |<--runs live----------|<--steps/messages----|
 |                  |--poll/ws----------->|                     |
 |                  |                      |--pytest evaluate    |
 |                  |                      |--finish_run(metrics)|
 |                  |<--completed---------|                     |
 |--排行榜 track--->|--GET leaderboard?track=frontend          |
```

---

## 26. 测试计划

### 26.1 后端单元

| 用例 | 期望 |
|------|------|
| `infer_track("html","feature",None)` | `frontend` |
| `infer_track("python","bugfix",None)` | `bugfix` |
| `infer_track("python","feature","algorithm")` | `algorithm`（显式优先） |
| `list_tasks(track="frontend")` | 仅 html 打标任务 |
| arena body track 与 task 不一致 | 400 |
| leaderboard track=frontend | 不含 bugfix-only 模型纯 bug 分（若该模型无 frontend run） |

### 26.2 API 手工 / e2e

```bash
curl -s localhost:8000/api/v1/tracks | jq .
curl -s "localhost:8000/api/v1/tasks?track=frontend" | jq ".tasks[].id"
curl -s "localhost:8000/api/v1/leaderboard?track=frontend" | jq .
```

### 26.3 前端验收

1. 切换赛道，任务列表变化  
2. 未选任务无法开始  
3. 对战完成后 run 详情含 track  
4. 排行榜 tab 切换数据变化  
5. 中英文赛道名正常  

### 26.4 回归

- 不传 track 的旧客户端仍可 `POST /arena`（服务端推断）  
- 删除产出、OpenCode tools 面板、Docker 隔离不受影响  

---

## 27. Phase 1 任务拆解（可建 Issue）

| ID | 标题 | 优先级 | 依赖 |
|----|------|--------|------|
| T1 | 新增 `tracks.py` + 单测 | P0 | — |
| T2 | `Task`/`task_runner` 支持 track | P0 | T1 |
| T3 | 全部 `task.json` 打标 | P0 | T2 |
| T4 | API：tracks / tasks 过滤 / arena / leaderboard / run 字段 | P0 | T2 |
| T5 | `run_store` 持久化 track | P0 | T4 |
| T6 | 前端 types + api + store | P0 | T4 |
| T7 | ArenaView 赛道 UI | P0 | T6 |
| T8 | LeaderboardView 赛道 tabs | P0 | T6 |
| T9 | i18n zh/en | P0 | T7 |
| T10 | README 一节「评测赛道」链接本文档 | P1 | T8 |
| T11 | Phase 2：tools_policy | P2 | T4 |
| T12 | Phase 2：algorithm/tooluse 样题 | P2 | T11 |

---

## 27.1 Hard 题库（2026-07-19 已入库）

业界对标：LiveCodeBench Hard、SciCode、SWE-bench 迷你多文件、FeatureBench 风格长 feature。  
**唯一变量：** 同 track 内仅换模型；题面 / pytest / 工具策略冻结。

| ID | track | difficulty | 对标 | 路径 |
|----|-------|------------|------|------|
| `algorithm-lfu-cache` | algorithm | hard | LeetCode 460 / LCB 风格 | `tasks/python/algorithm-lfu-cache/` |
| `algorithm-max-flow` | algorithm | hard | 竞赛最大流 | `tasks/python/algorithm-max-flow/` |
| `algorithm-rk4-orbit` | algorithm | hard | SciCode 数值 RK4 | `tasks/python/algorithm-rk4-orbit/` |
| `bugfix-event-dispatcher` | bugfix | hard | 多文件迷你 SWE | `tasks/python/bugfix-event-dispatcher/` |
| `feature-mvcc-store` | feature | hard | FeatureBench 级 | `tasks/python/feature-mvcc-store/` |

验收：starter/buggy 实现下 pytest 失败；参考正确实现下全绿（本地已核验）。

---

## 28. 发布检查清单

- [ ] 所有现有任务含 `track`  
- [ ] `GET /tracks` 返回 enabled + beta  
- [ ] Arena 无控制台报错  
- [ ] 至少 1 场 frontend 对战 run.track=frontend  
- [ ] 排行榜 frontend 与 all 结果可区分  
- [ ] 文档 §14/§16 决策与代码一致  
- [ ] （可选）`docs/eval-tracks-implementation.md` 在 README 导航中可点  

---

## 29. 附录 A — 排行榜 SQL/内存伪查询

当前为内存 `RunStore`，等价逻辑：

```python
def leaderboard(track: str = "all", score_type: str = "overall"):
    runs = [r for r in STORE.list_runs() if r.status == "completed"]
    if track != "all":
        runs = [r for r in runs if (r.track or infer_from_task(r.task_id)) == track]
    by_model = group_by(runs, key=lambda r: r.model_id)
    return [score_model(m, rs, score_type) for m, rs in by_model.items()]
```

历史 run 无 `track` 字段时：用 `task_id → get_task → track` 回填；任务已删则归入 `feature` 或丢弃并打日志。

---

## 30. 附录 B — UI 组件建议（可选）

```
components/
  TrackTabs.vue      # 通用赛道切换（Arena + Leaderboard 复用）
  TrackBadge.vue     # 任务卡片上的小徽章
```

`TrackTabs` props：

```ts
{ tracks: TrackInfo[], modelValue: string, showAll?: boolean, showBeta?: boolean }
```

---

## 31. 文档维护

| 变更 | 更新本文档章节 |
|------|----------------|
| 新增赛道 | §3、§18、§19、i18n |
| 改计分公式 | §5、§22 |
| tools_policy 上线 | §23、§11 fingerprint |
| 任务迁移物理目录 | §9、§18 |

**文档路径：** `llm-arena/docs/eval-tracks-implementation.md`
