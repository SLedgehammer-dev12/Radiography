# Radiography Project Guidelines

This project follows the **Ponytail (Lazy Senior Developer)** principles defined in [AGENTS.md](AGENTS.md) and [.agents/rules/ponytail.md](.agents/rules/ponytail.md), integrated with the **Agent Skills** architecture from [Addy Osmani's agent-skills](https://github.com/addyosmani/agent-skills).

## Core Principles
1. **The best code is the code never written**: Solve problems with the minimum necessary code.
2. **Standard library & existing code first**: Reuse existing helpers in `src/` and Python/Web standard libraries before introducing new abstractions or dependencies.
3. **Never cut essentials**: Preserve safety boundaries, physical/radiographic validation formulas (ASME / ISO standards), error handling, and test checks.
4. **Lifecycle & Orchestration**: Follow the 6-phase engineering lifecycle:
   - **DEFINE**: `/spec`, `interview-me` (spec before code)
   - **PLAN**: `/plan`, `planning-and-task-breakdown` (atomic verifiable tasks)
   - **BUILD**: `/build`, `incremental-implementation` (lean, test-driven implementation)
   - **VERIFY**: `/test`, `test-driven-development` (Prove-It bug pattern, test verification)
   - **REVIEW**: `/review` (5-axis software review) and `/ponytail-review` (RT calculation & zero-bloat review)
   - **SHIP**: `/ship` (parallel fan-out to `code-reviewer`, `security-auditor`, `test-engineer` [+ `rt-review`])
5. **Specialist Subagents**:
   - `rt-research`: Radiography codebase & architecture mapper (read-only)
   - `rt-review`: RT standard calculation & ISO/ASME physics reviewer (read-only)
   - `code-reviewer`: Senior Staff 5-axis code reviewer (read-only)
   - `security-auditor`: Security engineer, OWASP Top 10 & input boundaries (read-only)
   - `test-engineer`: QA & test strategy engineer (test suites & coverage)
   - `web-performance-auditor`: Web vitals & rendering performance auditor
   Configured in `.agents/agents/` for Antigravity and mirrored in `.opencode/agents/` for OpenCode.
6. **Skills & Slash Commands**:
   - Discovered via `.agents/skills/` for Antigravity and mirrored in `.opencode/skills/` and `.opencode/command/` for OpenCode.
   - Slash commands available in OpenCode: `/spec`, `/plan`, `/planning`, `/build`, `/test`, `/review`, `/ship`, `/code-simplify`, `/webperf`, `/constraints`, `/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`, `/ponytail-gain`, `/ponytail-help`, `/repo-indexer`.
