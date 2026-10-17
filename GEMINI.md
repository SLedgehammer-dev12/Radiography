# Radiography Project Guidelines

This project follows the **Ponytail (Lazy Senior Developer)** principles defined in [AGENTS.md](AGENTS.md) and [.agents/rules/ponytail.md](.agents/rules/ponytail.md).

## Core Principles
1. **The best code is the code never written**: Solve problems with the minimum necessary code.
2. **Standard library & existing code first**: Reuse existing helpers in `src/` and Python/Web standard libraries before introducing new abstractions or dependencies.
3. **Never cut essentials**: Preserve safety boundaries, physical/radiographic validation formulas (ASME / ISO standards), error handling, and test checks.
4. **Skills available**: Use `/ponytail` (lite/full/ultra), `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`, `/ponytail-gain`, and `/ponytail-help`.
5. **Subagents**: `rt-review` (read-only change review) and `rt-research` (read-only codebase mapping), configured in `.agents/agents/` for Antigravity and mirrored in `.opencode/agents/` for OpenCode with read-only permissions (`permission.edit: deny`, `permission.bash: deny`).
6. **Skills & Slash Commands**: Discovered via `.agents/skills/` for Antigravity, and mirrored in `.opencode/skills/` and `.opencode/command/` for OpenCode (`repo-indexer` and `ponytail*`).
