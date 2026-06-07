# CLI Reference

dbdocs is a [click](https://click.palletsprojects.com/) group with three
sub-commands. Run `dbdocs --help` or `dbdocs <command> --help` for the canonical,
always-up-to-date option list.

```bash
dbdocs --version
dbdocs --help
```

## Global options

| Option              | Description                       |
|---------------------|-----------------------------------|
| `-c, --config PATH` | Path to `dbdocs.yml`.             |
| `--version`         | Show the dbdocs version and exit. |
| `-h, --help`        | Show help and exit.               |

## `dbdocs generate`

Build the self-contained site from your dbt artifacts.

```bash
dbdocs generate
dbdocs generate -o public --dialect snowflake
```

| Option               | Description                                            |
|----------------------|--------------------------------------------------------|
| `-o, --output-dir`   | Where to write the site (overrides config).            |
| `--dialect`          | SQL dialect for column lineage (overrides `adapter_type`). |

Outputs `index.html` (everything baked in) plus a `dbdocs-data.json` companion
into the output directory.

## `dbdocs serve`

Serve the generated output directory over a static HTTP server. No live reload —
re-run `generate` and refresh.

```bash
dbdocs serve
dbdocs serve --port 9000
```

| Option         | Default | Description     |
|----------------|---------|-----------------|
| `-p, --port`   | `8000`  | Port to serve on. |

## `dbdocs deploy`

Generate a versioned build and maintain the version index. The result is a plain
directory layout any static host serves as-is — see
[Versioned Deploy](./versioned-deploy.md).

```bash
dbdocs deploy --version 1.2 --alias latest
dbdocs deploy --version 1.2 --delete
dbdocs deploy --version 1.2 --alias latest --push
```

| Option                | Default    | Description                                       |
|-----------------------|------------|---------------------------------------------------|
| `--version`           | *required* | Version label to deploy (e.g. `1.2`).             |
| `--alias`             | —          | Moving alias for this version (e.g. `latest`).    |
| `--title`             | the version| Display title for this version.                   |
| `--delete`            | off        | Delete this version instead of deploying it.      |
| `--push / --no-push`  | `--no-push`| Publish to the `gh-pages` branch (opt-in).        |

`--version` and `--alias` must match `[A-Za-z0-9._-]+` and cannot be `.` or
`..` — no spaces, slashes, or path separators. Invalid values raise a
`DeployError` before any files are touched.
