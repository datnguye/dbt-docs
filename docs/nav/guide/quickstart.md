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
    parquet information schema and switch dbdocs onto it in `dbdocs.yml`:

    ```bash
    pip install "dbdocs[info-schema]"
    dbt build --generate-info-schema        # writes target/info_schema/v1/
    echo "info_schema: true" >> dbdocs.yml
    ```

    [dbt 2.0 & Info Schema](./dbt-2-info-schema.md) walks through it: dbt Fusion
    vs dbt Core, how the parquet and JSON artifacts combine, and what to do when
    something looks off.

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
