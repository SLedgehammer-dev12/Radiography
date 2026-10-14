---
name: repo-indexer
description: >-
  Repository Indexer specialist for scanning codebase directory structures, mapping entry points,
  graphing module dependencies, detecting change hotspots, and generating token-efficient index documents
  (PROJECT_INDEX.md and PROJECT_INDEX.json) for AI-assisted development workflows.
---

# Repository Indexer Skill

This skill guides the agent in systematically indexing a repository, generating structural maps, internal and external dependency graphs, change hotspot intelligence, and token-efficient architectural summaries.

## Core Capabilities
1. **Freshness Assessment**: Evaluates existing `PROJECT_INDEX.md` and `PROJECT_INDEX.json` against staleness thresholds (default: 7 days or 15+ commits).
2. **Directory & Focus Area Mapping**: Scans source code, tests, configuration, documentation, and tooling scripts to establish a hierarchical taxonomy.
3. **Entry Point & Service Boundary Tracing**: Identifies primary application runners (Desktop, Web, Mobile, CLI) and their interaction surfaces.
4. **Dependency & Coupling Analysis**: Maps internal module imports (fan-in/fan-out) and catalogs external dependencies.
5. **Change Hotspot & Churn Detection**: Mines git commit history for high-churn files, bug-fix recurrence, and logical co-changes.
6. **Token-Efficient Context Generation**: Produces tiered summaries (Tier 1 Minimal, Tier 2 Standard, Tier 3 Detailed) optimized for LLM context windows.

---

## Step-by-Step Workflow

### 1. Freshness Check
- Verify presence of `PROJECT_INDEX.md` and `PROJECT_INDEX.json` in the project root.
- Check `git rev-parse HEAD` and timestamp of last indexing.
- If drift is below threshold, confirm validity; otherwise proceed to index generation.

### 2. Repository Scanning
- Categorize files into the 5 core domains:
  - Source Code (`src/`, `web/src/`, etc.)
  - Test Suites (`tests/`, `web/tests/`, etc.)
  - Configuration (`pyproject.toml`, `package.json`, `.github/`, etc.)
  - Documentation (`docs/`, `*.md`, etc.)
  - Scripts & Tools (`tools/`, `scripts/`, etc.)
- Exclude generated artifacts, caches, and vendor packages (`node_modules/`, `dist/`, `build/`, `__pycache__/`).

### 3. Entry Points & Service Interfaces
- Map server bootstrap, desktop GUI entry points, web worker bridges, mobile application runners, and CLI scripts.
- Trace data flow and facade boundaries (e.g., core calculation engines, UI controllers).

### 4. Dependency Graphing
- Calculate module coupling metrics:
  - **Fan-In**: Number of incoming module dependencies (centrality/reusability).
  - **Fan-Out**: Number of outgoing module dependencies (coupling/coordination).
  - **Instability Index**: $I = \frac{\text{Fan-Out}}{\text{Fan-In} + \text{Fan-Out}}$.

### 5. Change Hotspot & Churn Analysis
- Run `git log --name-only` to locate files with the highest commit frequency.
- Run `git log --grep=fix` to locate recurring bug hotspots.
- Identify co-changing file pairs (logical coupling).

### 6. Document Generation & Verification
- Generate `PROJECT_INDEX.md` (human/LLM readable).
- Generate `PROJECT_INDEX.json` (machine-parseable schema).
- Validate that all paths exist and no credentials/secrets are exposed.
