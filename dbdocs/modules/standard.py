import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from dbterd.api import DbtErd
from dbterd.helpers import file
from jinja2 import Environment, FileSystemLoader

from dbdocs.modules.base import BaseTemplate


def generate():
    StandardTemplate().generate()


class StandardTemplate(BaseTemplate):
    def __init__(self) -> None:
        super().__init__(module=__name__)

    def generate(self):
        target_path = os.path.join(Path.cwd(), "target")

        print("dbt docs generate")  # optional

        print("copy /target to /target/dbt-docs")  # optional

        print(f"copy {self.template_dir} to {target_path}")
        shutil.copytree(
            src=self.template_dir,
            dst=target_path,
            dirs_exist_ok=True,
        )

        print("read manifest + read catalog")
        manifest = file.read_manifest(path=target_path)
        catalog = file.read_catalog(path=target_path)

        print("jinja2 generate mkdocs.yml to /target")
        env = Environment(
            loader=FileSystemLoader(target_path),
        )
        mkdocs_file_path = os.path.join(target_path, "mkdocs.yml")
        mkdocs_data = dict(
            site_name="MVP Demo",
            site_url="https://github.com/datnguye/dbt-docs",
            site_author="Dat Nguyen",
            site_description="MVP Demo",
            repo_name="datnguye/dbt-docs",
            repo_url="https://github.com/datnguye/dbt-docs",
            project_name="MVP Demo",
            page_groups=[
                dict(
                    title="Models",
                    pages=[dict(title="Page", file_path="page-template.md")],
                )
            ],
        )
        with open(mkdocs_file_path, "w", encoding="utf-8") as f:
            f.write(env.get_template("mkdocs-template.yml").render(**mkdocs_data))

        print("jinja2 generate index.md to /target/docs")
        index_file_path = os.path.join(target_path, "docs/index.md")
        index_data = dict(
            project_name="MVP Demo",
            generated_at=datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S"),
            erd=DbtErd(target="mermaid").get_erd(),
        )
        with open(index_file_path, "w", encoding="utf-8") as f:
            f.write(env.get_template("docs/index-template.md").render(**index_data))

        print("jinja2 generate selected page.md files to /target/docs")

        print("cd to /target + mike build to /site")
        subprocess.run(["mkdocs", "build"], cwd=target_path)
        subprocess.run(["mkdocs", "serve"], cwd=target_path)
        return super().generate()
