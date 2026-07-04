# Contributing Guide

Thanks for wanting to make dbdocs better! Bugs, features, docs, typos — all
welcome here. 🎉

## Project setup

dbdocs uses [uv](https://docs.astral.sh/uv/) for the Python environment and
[Task](https://taskfile.dev/) as the command runner. Slash commands and CI wrap
the same Task targets, so the manual and automated paths stay aligned.

```bash
# Clone and enter
git clone https://github.com/datnguye/dbt-docs.git
cd dbt-docs

# Sync the environment (incl. dev group)
task install

# Install git hooks (pre-commit + commit-msg)
task git-hooks
```

`task --list` shows everything available.

## The day-to-day loop

| Goal                              | Task             |
|-----------------------------------|------------------|
| Sync the uv environment           | `task install`   |
| Format + autofix                  | `task format`    |
| Lint (format-check + ruff)        | `task lint`      |
| Run tests at 100% coverage        | `task test`      |
| Build the self-contained site     | `task generate`  |
| Serve the generated site locally  | `task serve`     |
| Deploy a versioned build          | `task deploy`    |

## Code standards

These are enforced — CI will fail otherwise:

- **`task lint` must pass** — `ruff format --check` and `ruff check`.
- **100% test coverage** — `task test` runs the gate. Vendored third-party code
  (`extract/_sqlglot_lineage.py`) is omitted from coverage, never gamed with
  no-cover pragmas.
- **No relative imports**, all imports at module top (`ruff PLC0415` enforces).
- **One class per file** (exception: multiple exception classes may share one).
  No nested functions/classes.
- **Specific exception types** in `try/except` — never bare `except:` /
  `except Exception`.
- **No backward-compat shims** unless explicitly asked.
- **DRY in tests** — share fixtures via `tests/conftest.py`.

## Working on the graph UI

The interactive DAG and ERD live under `frontend/` (React + TypeScript, Vite)
and compile to the committed bundle at `dbdocs/site/bundle/assets/graph/`.
Graph-UI changes need Node:

```bash
task frontend:install     # npm ci
task frontend:build       # rebuild the committed bundle — commit the output
task frontend:test        # vitest
```

`dbdocs generate` stays pure-Python and build-step-free — it just copies that
prebuilt bundle.

## Agentic tooling

This repo ships a Claude Code setup under `.claude/` — agents, skills, commands,
and hooks (see the [Agentic setup](https://github.com/datnguye/dbt-docs/blob/main/CLAUDE.md#agentic-setup)
section of `CLAUDE.md`). Two Claude Code **plugins** are enabled for the project
in `.claude/settings.json` (`enabledPlugins`); if you work with Claude Code
against this repo they load automatically:

| Plugin | Marketplace | What it does |
|--------|-------------|--------------|
| `frontend-design` | `claude-plugins-official` | Frontend design skill for the graph-UI (`frontend/`) work |
| `oh-my-statusline` | `infinitelambda` | Status line: model, context %, session cost, duration, lines changed |

Plugins are optional developer ergonomics — you can contribute without them. Any
personal enable/disable overrides belong in the gitignored
`.claude/settings.local.json`, not the shared `settings.json`.

## Submitting a pull request

1. Branch off `main`.
2. Make your change with tests; keep coverage at 100%.
3. Run `task lint && task test` locally.
4. Open a PR with a clear description. CI runs lint + tests across Python
   3.10–3.13.

For how the codebase is laid out, see
[`CLAUDE.md`](https://github.com/datnguye/dbt-docs/blob/main/CLAUDE.md) and
[`.claude/design_patterns.md`](https://github.com/datnguye/dbt-docs/blob/main/.claude/design_patterns.md)
in the repo.
