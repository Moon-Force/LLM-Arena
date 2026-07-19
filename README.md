# LLM Arena

**Fair multi-model coding-agent arena** powered by official [OpenCode](https://www.npmjs.com/package/opencode-ai).

> Same tasks · same tools · same constraints — **only the model changes** (single-variable principle).

[![License](https://img.shields.io/badge/license-see%20repo-blue)](./llm-arena)
[![OpenCode](https://img.shields.io/badge/engine-opencode--ai-orange)](https://www.npmjs.com/package/opencode-ai)
[![Stack](https://img.shields.io/badge/stack-Vue3%20%7C%20FastAPI%20%7C%20Docker-informational)](./llm-arena)

## Keywords

`LLM benchmark` · `coding agent` · `OpenCode` · `SWE-bench style` · `multi-model evaluation` · `pytest` · `fair arena` · `agent leaderboard` · `bugfix` · `frontend eval`

## Why LLM Arena?

| Need | How this project helps |
|------|-------------------------|
| Compare coding agents fairly | Freeze tools, system prompt, temperature, steps |
| Real agent loop (not toy chat) | Official `opencode serve` + full tool set |
| Hard tasks | Algorithm / bugfix / feature / frontend tracks |
| Auto score | Workspace `pytest` (fail→pass style) |
| Author tasks in UI | Task Lab at `/tasks` |

## Quick start

```bash
cd llm-arena
# backend
python -m venv venv
# Windows: .\venv\Scripts\activate
pip install -r requirements.txt
python -m opencode.api.server

# frontend (another terminal)
npm install
npm run dev
```

- UI: http://127.0.0.1:3000  
- API: http://127.0.0.1:8000/docs  

Full docs: [llm-arena/README.md](./llm-arena/README.md) · [eval tracks](./llm-arena/docs/eval-tracks-implementation.md)

## Repository layout

```text
LLM-Arena/
  llm-arena/          # app (Vue + FastAPI + tasks/)
    tasks/            # evaluation tasks (task.json + tests)
    opencode/         # API + OpenCode runtime
    src/              # frontend
    docs/             # design notes
```

## License

See project files under `llm-arena/`. Contributions welcome via issues / PRs.
