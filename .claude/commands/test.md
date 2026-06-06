---
description: Run the pytest suite with the 100% coverage gate and report pass/fail plus uncovered lines.
---

Run the suite:

```
uv run pytest --cov=dbdocs --cov-report=term-missing --cov-fail-under=100
```

Report:

| Result | Coverage | Notes                         |
|--------|----------|-------------------------------|
| ...    | ...%     | failing tests / uncovered lines |

If coverage is < 100%, list the uncovered `file:line` ranges. If tests fail,
show the failing test names and the assertion output. Do not attempt to fix
failures unless the user asks.
