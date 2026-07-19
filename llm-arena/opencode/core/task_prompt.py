"""Build rich, language-aware task prompts for the agent."""

from __future__ import annotations

from .task_runner import Task


def build_task_prompt(task: Task) -> str:
    """Expand task.json into an agent-facing brief for official OpenCode tools."""
    lines = [
        f"# Task: {task.name}",
        f"ID: {task.id}",
        f"Language: {task.language}",
        f"Type: {task.type}",
        f"Difficulty: {task.difficulty}",
        "",
        "## Description",
        task.description.strip(),
        "",
        "## Working directory",
        "Your tools operate in the current project workspace only.",
        "List / glob files first, then read existing sources, then edit/write.",
        "",
        "## Definition of done",
        "1. Implement or fix all required behavior.",
        "2. Ensure expected files exist: "
        + (", ".join(task.expected_files) if task.expected_files else "(see description)"),
        "3. Run tests with the bash tool:",
        "   python -m pytest -v --tb=short",
        "4. If tests fail, fix and re-run until they pass.",
        "5. When all tests pass, reply with the single word FINISHED.",
        "",
    ]

    if task.language in ("html", "typescript", "javascript", "css"):
        lines.extend(
            [
                "## Frontend / UI rules",
                "- Prefer a complete working `index.html` (inline <style> and <script> OK).",
                "- You may also use styles.css / app.js if needed.",
                "- Keep required element ids/classes exactly as specified (tests check them).",
                "- Do not leave TODO placeholders or 'stub' titles in the final page.",
                "- After writing HTML, run pytest to verify structure.",
                "",
            ]
        )

    if task.track == "algorithm" or task.type in ("algorithm", "algo", "function"):
        lines.extend(
            [
                "## Algorithm track rules (single-variable fairness)",
                "- Solve from the task description and local files only.",
                "- Do not use webfetch/websearch to look up solutions.",
                "- Keep the public function/class names required by tests.",
                "",
            ]
        )

    lines.extend(
        [
            "## Tools (official OpenCode — full set)",
            "bash, read, write, edit, apply_patch, grep, glob, list,",
            "webfetch, websearch, todowrite, skill, lsp, task.",
            "Do not invent custom fenced ```tool blocks — call the real tools.",
            "Do not ask interactive questions; this run is unattended.",
        ]
    )
    return "\n".join(lines)
