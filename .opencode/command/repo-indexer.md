---
description: "Scan codebase structure, map dependencies, detect change hotspots, and generate/update PROJECT_INDEX.md and PROJECT_INDEX.json"
---

Scan and index the repository systematically following the repo-indexer procedure:
1. Freshness Check: Check existing PROJECT_INDEX.md and PROJECT_INDEX.json against staleness thresholds (default: 7 days or 15+ commits).
2. Repository Scanning: Categorize files into Source Code (src/, web/src/), Test Suites (tests/, web/tests/), Configuration, Documentation, and Scripts/Tools. Exclude generated artifacts, caches, and vendor packages (node_modules/, dist/, build/, __pycache__/).
3. Entry Points & Boundaries: Map application runners (Desktop UI, Web bridge/worker, Mobile app_state, CLI) and their interaction surfaces.
4. Dependency Graphing: Map internal module imports (fan-in / fan-out) and catalog external dependencies.
5. Change Hotspots: Mine git commit history for high-churn files and recurring bug hotspots.
6. Document Generation: Generate/update PROJECT_INDEX.md and PROJECT_INDEX.json in the project root.
