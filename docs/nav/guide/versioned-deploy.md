# Versioned Deploy

dbdocs ships its own lightweight versioning — no mike, no plugins. A deploy is
just a directory layout any static host serves as-is, and the SPA reads a
`versions.json` to render a version dropdown.

## The layout

```
site/
  versions.json          # [{version, title, aliases}]
  1.2/index.html         # one generated site per version
  1.1/index.html
  latest/  ──▶ a copy of whichever version the "latest" alias points at
```

## Deploy a version

```bash
dbdocs deploy --version 1.2 --alias latest
```

This generates the site into `site/1.2/`, updates `site/versions.json`, and —
because `--alias latest` was given — copies the build into `site/latest/`. An
alias is *moving*: deploying `1.3 --alias latest` shifts `latest` off `1.2` and
onto `1.3` automatically.

!!! note "Label format"
    Both `--version` and `--alias` must match `[A-Za-z0-9._-]+` and cannot be
    `.` or `..`. No spaces, slashes, or other path separators are allowed —
    invalid values raise a `DeployError` before anything is written.

| Want to…                        | Command                                            |
|---------------------------------|----------------------------------------------------|
| Deploy and tag as latest        | `dbdocs deploy --version 1.2 --alias latest`       |
| Deploy a beta (no alias)        | `dbdocs deploy --version 1.3-beta`                 |
| Give a version a display title  | `dbdocs deploy --version 1.2 --title "1.2 (LTS)"`  |
| Remove a version + its aliases  | `dbdocs deploy --version 1.2 --delete`             |

When `--delete` is used, all aliases associated with the version are read back
from `versions.json` and validated against the same label rules before any
directory is removed.

## Publishing to GitHub Pages

`--push` is **opt-in** (off by default, since it's outward-facing). It commits
the output directory onto a `gh-pages` branch and force-pushes it:

```bash
dbdocs deploy --version 1.2 --alias latest --push
```

If any git step fails, dbdocs raises a `DeployError` rather than leaving you
guessing.

!!! tip "CI is the friendlier path"
    For automated publishing, drive `dbdocs deploy --push` from a GitHub Actions
    workflow with `contents: write` permission rather than pushing from your
    laptop. That keeps credentials in CI and your local git history clean.

## Custom domain

Point a `CNAME` at your Pages site (this project uses `dbdocs.datnguye.me`).
Keep a `CNAME` file in the published output so GitHub Pages preserves the domain
across deploys.
