# Configuration

All site settings live in an optional `dbdocs.yml` in your working directory.
Every key is optional — drop the file entirely to accept the defaults. Copy
[`dbdocs.yml.example`](https://github.com/datnguye/dbt-docs/blob/main/dbdocs.yml.example)
to `dbdocs.yml` and edit.

```bash
cp dbdocs.yml.example dbdocs.yml
```

## Site metadata

These keys control what's displayed in the generated site's header and footer.

| Key                   | Default                          | Purpose                                                   |
|-----------------------|----------------------------------|-----------------------------------------------------------|
| `site_name`           | `dbt docs`                       | Site title shown in the header.                           |
| `site_url`            | repo URL                         | Canonical site URL.                                       |
| `site_author`         | `Dat Nguyen`                     | Author metadata.                                          |
| `site_description`    | `Alternative dbt documentation site` | Site description metadata.                            |
| `repo_name`           | `datnguye/dbt-docs`              | Display name of the source repo.                          |
| `repo_url`            | repo URL                         | Link to the source repo.                                  |
| `project_name`        | `dbt docs`                       | dbt project display name.                                 |
| `show_buy_me_a_coffee`| `true`                           | Show the "Buy me a coffee" badge in the footer.           |
| `readme`              | `README.md`                      | Markdown file rendered on the overview, after the ERD. Set empty to omit; a missing file is silently skipped. |

## Build control

These keys control the generate/deploy pipeline rather than display.

| Key               | Default       | Purpose                                                          |
|-------------------|---------------|------------------------------------------------------------------|
| `target_dir`      | `target`      | Where dbt artifacts (`manifest.json` / `catalog.json`) are read from. |
| `output_dir`      | `target/site` | Where the generated site is written.                             |
| `dialect`         | adapter type  | SQL dialect override for column-level lineage parsing. Omit to derive from the artifact's `adapter_type` (snowflake, bigquery, postgres, …). |
| `default_version` | `latest`      | Alias the version switcher lands on.                             |

!!! note "`version` is not a config key"
    The deployed version is a `dbdocs deploy --version` argument, not a
    `dbdocs.yml` field. See [Versioned Deploy](./versioned-deploy.md).

## ERD options (dbterd passthrough)

dbdocs builds the ERD via the [dbterd](https://dbterd.datnguye.me/) Python API.
Anything you'd configure on `DbtErd` can go under a `dbterd:` block — using
**underscore** keys (not the kebab-case of a standalone `.dbterd.yml`). Omit the
block to use dbterd's defaults.

```yaml
dbterd:
  algo: model_contract          # FK detection: model contracts or relationship tests
  entity_name_format: model     # short node labels
  resource_type:
    - model
  select:
    - wildcard:model.my_project.mart_*
```

## Full example

```yaml
# dbdocs.yml — site configuration for `dbdocs`.
# Every key is optional; omit the file entirely to accept all defaults.

# Site display metadata.
site_name: dbt docs
site_url: https://github.com/datnguye/dbt-docs
site_author: Dat Nguyen
site_description: Alternative dbt documentation site
repo_name: datnguye/dbt-docs
repo_url: https://github.com/datnguye/dbt-docs
project_name: dbt docs

# Footer "Buy me a coffee" badge. Set false to suppress.
show_buy_me_a_coffee: true

# Project README rendered on the overview, after the ERD. Empty to omit.
readme: README.md

# dbt artifacts in / generated site out.
target_dir: target
output_dir: target/site

# SQL dialect for column-level lineage. Omit to derive from adapter_type.
# dialect: snowflake

# Default landing version for the switcher.
default_version: latest

# dbterd ERD options — passed straight to DbtErd (underscore keys).
# dbterd:
#   algo: model_contract
#   entity_name_format: model
#   resource_type:
#     - model
#   select:
#     - wildcard:model.my_project.mart_*
```
