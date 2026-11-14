# Quickstart

This walkthrough takes you from a dbt project to a browsable, hostable docs site
in three commands.

## 1. Generate dbt artifacts

dbdocs reads the two JSON files dbt emits — it never connects to your warehouse
or parses your project directly.

```bash
dbt docs generate           # writes target/manifest.json + target/catalog.json
```

!!! tip "Why both files?"
    `manifest.json` carries the graph (models, sources, tests, refs, compiled
    SQL); `catalog.json` carries the column types pulled from your warehouse.
    dbdocs needs both — the catalog is what makes `SELECT *` resolve in
    column-level lineage.

!!! note "On dbt 2.0?"
    dbt 2.0's `docs generate` no longer writes `catalog.json`. dbdocs still
    builds from `manifest.json` alone, just without warehouse column types and
    with thinner column-level lineage. For the full picture, have dbt write its
    parquet information schema and let dbdocs read that instead:

    ```bash
    pip install "dbdocs[info-schema]"
    dbt build --generate-info-schema        # writes target/info_schema/v1/
    dbdocs generate --info-schema
    ```

    With dbt Fusion, add `--static-analysis strict` to the dbt command and the
    info schema carries column-level lineage computed by dbt itself, which tends
    to see further than dbdocs can by reverse-engineering SQL. Any JSON artifacts lying
    around still help: they fill whatever the parquet leaves blank. See the
    [CLI Reference](./cli-references.md#dbdocs-generate) for how the two merge.

## 2. Generate the site

```bash
dbdocs generate             # builds ./site/index.html with all data baked in
```

This reads the artifacts (from `target/` by default), derives the documentation
data — catalog nodes, the lineage graph, the ERD, and column-level lineage — and
writes a single self-contained `site/index.html` plus a `site/dbdocs-data.json`
companion. Everything the SPA needs is base64-injected into that one HTML file,
so it works straight off the filesystem.

## 3. Serve it

```bash
dbdocs serve                # static http server on http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000> and browse. There's no live reload — change a model,
re-run `dbt docs generate` and `dbdocs generate`, then refresh.

## What next?

- Tune the site title, repo links, and SQL dialect in [Configuration](./configuration.md).
- Learn what each command does in the [CLI Reference](./cli-references.md).
- Ship a versioned site with a version switcher in [Versioned Deploy](./versioned-deploy.md).
