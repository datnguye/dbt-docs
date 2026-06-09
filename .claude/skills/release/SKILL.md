---
name: release
description: Use when cutting a release of the dbdocs package to PyPI. The single source of truth for the release procedure — pre-flight, version selection, GitHub Release creation, and post-publish verification.
---

# Releasing dbdocs to PyPI

Releases are **tag-driven**: creating a GitHub Release publishes a tag, CI on the
`release: published` event builds the wheel/sdist and publishes to PyPI. You never
publish from a local machine (`uv publish` / `twine upload` are denied in
`.claude/settings.json`).

## Pre-flight (must all pass on a clean `main`)

1. Working tree clean, on `main`, up to date with `origin/main`.
2. `task lint` — ruff format-check + lint pass.
3. `task test` — pytest at 100% coverage.
4. `uv build` produces a wheel **and** confirm the wheel contains the bundled
   SPA: `python -m zipfile -l dist/dbdocs-*.whl | grep dbdocs/site/bundle` should
   list `index.html` + the `assets/{js,css,vendor,graph}/` files. A wheel missing
   `dbdocs/site/bundle/**` is broken — fix the `artifacts` glob in
   `[tool.hatch.build.targets.wheel]` of `pyproject.toml` before releasing.

## Version selection

- `dbdocs` follows semver. Choose patch/minor/major from the changes since the
  last tag (`git log <last-tag>..HEAD`; `git tag --sort=-v:refname | head` shows
  the latest — the most recent published version is **1.0.2**).
- The version is **dynamic from the git tag** (`[tool.hatch.version] source =
  "vcs"`) — there is no static `version` in `pyproject.toml` to set. The tag you
  create *is* the version. Tags are **unprefixed** `X.Y.Z` (e.g. `1.0.2`), not
  `vX.Y.Z`.

## Cutting the release

1. Confirm the exact version with the user — **never** create a Release without
   explicit confirmation.
2. Generate release notes from the commit range (Conventional Commits → grouped
   highlights). Notes live in the **Release body**, not a `CHANGELOG.md`.
3. `gh release create X.Y.Z --title "X.Y.Z" --notes "<notes>"` — unprefixed tag
   (matching the existing `1.0.2` style); this creates the tag and fires CI.

## Post-publish verification

1. Watch the CI run (`gh run watch`); capture the run ID for memory.
2. Once green, verify the artifact installs from PyPI:
   `pip install dbdocs==X.Y.Z` in a throwaway env, then `dbdocs --version`.

## Cardinal rules

- **Never** force-push or delete a published tag/Release. To fix a bad release,
  cut a new patch version.
- **Never** publish to PyPI from a local machine — CI only.
- **Never** maintain a `CHANGELOG.md`.
