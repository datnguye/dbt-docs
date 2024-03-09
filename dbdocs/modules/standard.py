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

        env = Environment(
            loader=FileSystemLoader(target_path),
        )
        print("jinja2 generate mkdocs.yml to /target")
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
                    pages=[
                        dict(
                            title=manifest.nodes[x].unique_id.split('.')[-1], 
                            file_path=f"models/{manifest.nodes[x].unique_id.split('.')[-1]}.md"
                        )
                        for x in manifest.nodes
                        if str(x).startswith("model")
                    ],
                ),
                dict(
                    title="Sources",
                    pages=[
                        dict(
                            title=manifest.sources[x].unique_id.split('.')[-1], 
                            file_path=f"sources/{manifest.sources[x].unique_id.split('.')[-1]}.md"
                        )
                        for x in manifest.sources
                    ],
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
        for node in manifest.nodes:
            if str(node).startswith("model"):
                model = manifest.nodes[node]
                model_manifest_columns = manifest.nodes[node].columns
                model_catalog_columns = catalog.nodes[node].columns
                model_file_path = os.path.join(target_path, f"docs/models/{model.unique_id.split('.')[-1]}.md")
                model_data = dict(
                    model_id=model.unique_id,
                    model_description=model.description,
                    model_tags=model.tags,
                    model_erd=DbtErd(target="mermaid").get_model_erd(model.unique_id),
                    columns=[
                        dict(
                            name=x,
                            type=model_catalog_columns[x].type,
                            tags=model_manifest_columns[x].tags if x in model_manifest_columns else "",
                            description=(model_manifest_columns[x].description if x in model_manifest_columns else "").replace("\n", "<br>")
                        )
                        for x in model_catalog_columns
                    ]
                )
                Path(f"{target_path}/docs/models").mkdir(parents=True, exist_ok=True) 
                with open(model_file_path, "w", encoding="utf-8") as f:
                    f.write(env.get_template("docs/page-template.md").render(**model_data))
                    
        for node in manifest.sources:
            model = manifest.sources[node]
            model_manifest_columns = manifest.sources[node].columns
            model_catalog_columns = catalog.sources[node].columns if node in catalog.sources else {}
            model_file_path = os.path.join(target_path, f"docs/sources/{model.unique_id.split('.')[-1]}.md")
            model_data = dict(
                model_id=model.unique_id,
                model_description=model.description,
                model_tags=model.tags,
                model_erd=DbtErd(target="mermaid").get_model_erd(model.unique_id),
                columns=[
                    dict(
                        name=x,
                        type=model_catalog_columns[x].type,
                        tags=model_manifest_columns[x].tags if x in model_manifest_columns else "",
                        description=(model_manifest_columns[x].description if x in model_manifest_columns else "").replace("\n", "<br>")
                    )
                    for x in model_catalog_columns
                ]
            )
            Path(f"{target_path}/docs/sources").mkdir(parents=True, exist_ok=True) 
            with open(model_file_path, "w", encoding="utf-8") as f:
                f.write(env.get_template("docs/page-template.md").render(**model_data))

        print("cd to /target + mike build to /site")
        subprocess.run(["mkdocs", "build"], cwd=target_path)
        subprocess.run(["mkdocs", "serve"], cwd=target_path)
        return super().generate()
