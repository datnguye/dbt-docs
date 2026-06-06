"""Versioned deploy of the generated site.

Versioning is a plain directory layout that any static host (GitHub Pages, S3,
…) serves as-is — no external tooling:

    site/
      versions.json          # [{version, title, aliases}]
      <version>/index.html   # one generated site per version
      <alias>/  -> copy of the version a moving alias points at (e.g. latest)

``deploy`` generates into ``site/<version>/``, updates ``versions.json``, and
copies the build to each alias dir. ``--push`` (opt-in, outward-facing) commits
the output dir onto a ``gh-pages`` branch and pushes it.
"""

import json
import subprocess
from pathlib import Path
from shutil import copytree, rmtree

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DeployError
from dbdocs.core.log import logger
from dbdocs.site.builder import ReportBuilder

VERSIONS_FILE = "versions.json"


def _read_versions(output_root: Path) -> list:
    path = output_root / VERSIONS_FILE
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _upsert_version(versions: list, version: str, title: str, alias: "str | None") -> list:
    """Merge ``version`` into the list, moving ``alias`` to it and off others."""
    versions = [v for v in versions if v.get("version") != version]
    if alias:
        for entry in versions:
            entry["aliases"] = [a for a in entry.get("aliases", []) if a != alias]
    aliases = [alias] if alias else []
    versions.append({"version": version, "title": title, "aliases": aliases})
    versions.sort(key=lambda v: v["version"], reverse=True)
    return versions


def deploy(
    config: DbDocsConfig,
    version: str,
    alias: "str | None" = None,
    push: bool = False,
    title: "str | None" = None,
) -> str:
    """Generate ``version`` into the output root and update the version index."""
    output_root = Path(config.output_path)
    version_dir = output_root / version
    if version_dir.exists():
        rmtree(version_dir)

    ReportBuilder(config).generate(output_dir=str(version_dir))

    versions = _upsert_version(_read_versions(output_root), version, title or version, alias)
    (output_root / VERSIONS_FILE).write_text(json.dumps(versions, indent=2), encoding="utf-8")

    if alias:
        alias_dir = output_root / alias
        if alias_dir.exists():
            rmtree(alias_dir)
        copytree(src=version_dir, dst=alias_dir)
        logger.info("Aliased %s → %s", alias, version)

    logger.info("Deployed version %s into %s", version, version_dir)
    if push:
        _push_gh_pages(output_root, version)
    return str(version_dir)


def delete(config: DbDocsConfig, version: str, push: bool = False) -> None:
    """Remove a deployed ``version`` — its dir, index entry and any aliases.

    Raises :class:`DeployError` if the version isn't deployed.
    """
    output_root = Path(config.output_path)
    versions = _read_versions(output_root)
    entry = next((v for v in versions if v.get("version") == version), None)
    if entry is None:
        raise DeployError(f"Version {version!r} is not deployed.")

    version_dir = output_root / version
    if version_dir.exists():
        rmtree(version_dir)
    for alias in entry.get("aliases", []):
        alias_dir = output_root / alias
        if alias_dir.exists():
            rmtree(alias_dir)

    remaining = [v for v in versions if v.get("version") != version]
    (output_root / VERSIONS_FILE).write_text(json.dumps(remaining, indent=2), encoding="utf-8")

    logger.info("Deleted version %s", version)
    if push:
        _push_gh_pages(output_root, version)


def _push_gh_pages(output_root: Path, version: str) -> None:
    """Publish ``output_root`` to the ``gh-pages`` branch (opt-in)."""
    commands = [
        ["git", "checkout", "-B", "gh-pages"],
        ["git", "add", "--force", str(output_root)],
        ["git", "commit", "-m", f"deploy docs version {version}"],
        ["git", "push", "--force", "origin", "gh-pages"],
    ]
    for cmd in commands:
        try:
            subprocess.run(cmd, check=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            raise DeployError(f"`{' '.join(cmd)}` failed: {exc}") from exc
    logger.info("Pushed gh-pages.")
