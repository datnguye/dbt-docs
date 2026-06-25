"""Shared fixtures.

These build lightweight stand-ins for the ``dbterd`` manifest/catalog objects so
the extract + site-building logic can be exercised without a real dbt project.
The fakes mirror only the attributes the code touches. The dbt ``schema`` field
is exposed as ``schema_`` (the Pydantic alias) — code reads ``schema_``, never
``schema``.
"""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbdocs.core.config import DbDocsConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"
JAFFLE_SHOP_ARTIFACTS = FIXTURES_DIR / "jaffle_shop"
RUN_RESULTS = JAFFLE_SHOP_ARTIFACTS / "run_results.json"
BIG_PROJECT_ARTIFACTS = FIXTURES_DIR / "big_project"


@pytest.fixture
def config(tmp_path):
    """A config whose target/output dirs point at fresh tmp dirs."""
    return DbDocsConfig(target_dir=str(tmp_path / "target"), output_dir=str(tmp_path / "site"))


@pytest.fixture
def run_results_path():
    """Path to the sanitized plain-dbt run_results.json fixture (29 tests)."""
    return RUN_RESULTS


@pytest.fixture
def jaffle_project(tmp_path, monkeypatch):
    """A throwaway dbt project: cwd with a target/ holding the real v12 artifacts."""
    target = tmp_path / "target"
    target.mkdir()
    for name in ("manifest.json", "catalog.json"):
        shutil.copy(JAFFLE_SHOP_ARTIFACTS / name, target / name)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def big_project(tmp_path, monkeypatch):
    """A throwaway dbt project staging the larger real v12 artifacts (96 models,
    149 tests, snowflake) — exercises generate at scale."""
    target = tmp_path / "target"
    target.mkdir()
    for name in ("manifest.json", "catalog.json"):
        shutil.copy(BIG_PROJECT_ARTIFACTS / name, target / name)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def column(name, type_="varchar", tags=None, description=""):
    return SimpleNamespace(name=name, type=type_, tags=tags or [], description=description)


def make_test_node(*, test_type=None, attached_node=None, column_name=None):
    """A manifest test-node fake (``test.*`` prefix). Mirrors the fields the test
    extractor and column-tests index read: ``test_metadata.name``,
    ``attached_node``, ``column_name``."""
    metadata = SimpleNamespace(name=test_type) if test_type is not None else None
    return SimpleNamespace(
        test_metadata=metadata,
        attached_node=attached_node,
        column_name=column_name,
    )


def node(
    unique_id,
    columns=None,
    *,
    database="db",
    schema="analytics",
    description="desc",
    tags=None,
    relation_name=None,
    package_name="shop",
    language="sql",
    raw_code="",
    compiled_code="",
    depends_on_nodes=None,
    depends_on_macros=None,
    name=None,
    alias=None,
    materialization="view",
    meta=None,
    access="",
    group="",
    contract_enforced=False,
    version=None,
    latest_version=None,
    owner=None,
    original_file_path="",
    patch_path="",
):
    """A manifest node/source fake. ``schema`` is stored as ``schema_`` (alias)."""
    short = unique_id.split(".")[-1]
    return SimpleNamespace(
        unique_id=unique_id,
        name=name or short,
        alias=alias,
        database=database,
        schema_=schema,
        description=description,
        tags=tags or [],
        relation_name=relation_name
        if relation_name is not None
        else f"{database}.{schema}.{short}",
        package_name=package_name,
        language=language,
        raw_code=raw_code,
        compiled_code=compiled_code,
        columns=columns or {},
        depends_on=SimpleNamespace(nodes=depends_on_nodes or [], macros=depends_on_macros or []),
        config=SimpleNamespace(materialized=materialization, meta=meta or {}),
        meta=meta or {},
        access=access,
        group=group,
        contract=SimpleNamespace(enforced=contract_enforced),
        version=version,
        latest_version=latest_version,
        owner=owner,
        original_file_path=original_file_path,
        patch_path=patch_path,
    )


def macro(unique_id, macro_sql="{% macro m() %}{% endmacro %}", package_name="shop"):
    return SimpleNamespace(
        unique_id=unique_id,
        name=unique_id.split(".")[-1],
        package_name=package_name,
        macro_sql=macro_sql,
    )


def metric_entity(
    unique_id,
    *,
    metric_type="simple",
    label="",
    description="",
    group="",
    tags=None,
    depends_on_nodes=None,
    filter_val=None,
    type_params=None,
):
    """A manifest metric fake."""
    return SimpleNamespace(
        name=unique_id.split(".")[-1],
        label=label,
        description=description,
        type=metric_type,
        type_params=type_params,
        filter=filter_val,
        group=group,
        tags=tags or [],
        meta={},
        package_name=unique_id.split(".")[1] if unique_id.count(".") >= 2 else "shop",
        depends_on=SimpleNamespace(nodes=depends_on_nodes or []),
    )


def semantic_model_entity(
    unique_id,
    *,
    model="",
    description="",
    depends_on_nodes=None,
    entities=None,
    dimensions=None,
    measures=None,
    tags=None,
):
    """A manifest semantic_model fake."""
    return SimpleNamespace(
        name=unique_id.split(".")[-1],
        description=description,
        model=model,
        entities=entities or [],
        dimensions=dimensions or [],
        measures=measures or [],
        tags=tags or [],
        meta={},
        package_name=unique_id.split(".")[1] if unique_id.count(".") >= 2 else "shop",
        depends_on=SimpleNamespace(nodes=depends_on_nodes or []),
    )


def saved_query_entity(
    unique_id,
    *,
    label="",
    description="",
    metrics=None,
    group_by=None,
    where=None,
    exports=None,
    depends_on_nodes=None,
    tags=None,
):
    """A manifest saved_query fake."""
    query_params = SimpleNamespace(
        metrics=metrics or [],
        group_by=group_by or [],
        where=where or [],
    )
    return SimpleNamespace(
        name=unique_id.split(".")[-1],
        label=label,
        description=description,
        query_params=query_params,
        exports=exports or [],
        tags=tags or [],
        meta={},
        package_name=unique_id.split(".")[1] if unique_id.count(".") >= 2 else "shop",
        depends_on=SimpleNamespace(nodes=depends_on_nodes or []),
    )


def unit_test_entity(
    unique_id, *, model="", description="", given=None, expect=None, depends_on_nodes=None
):
    """A manifest unit_test fake."""
    return SimpleNamespace(
        name=unique_id.split(".")[-1],
        model=model,
        description=description,
        given=given or [],
        expect=expect,
        tags=[],
        meta={},
        package_name=unique_id.split(".")[1] if unique_id.count(".") >= 2 else "shop",
        depends_on=SimpleNamespace(nodes=depends_on_nodes or []),
    )


def exposure_entity(
    unique_id,
    *,
    exposure_type="dashboard",
    label="",
    description="",
    maturity="",
    url="",
    owner_name="",
    owner_email="",
    depends_on_nodes=None,
    tags=None,
):
    """A manifest exposure fake."""
    owner = SimpleNamespace(name=owner_name, email=owner_email)
    return SimpleNamespace(
        name=unique_id.split(".")[-1],
        type=exposure_type,
        label=label,
        description=description,
        maturity=maturity,
        url=url,
        owner=owner,
        tags=tags or [],
        meta={},
        package_name=unique_id.split(".")[1] if unique_id.count(".") >= 2 else "shop",
        depends_on=SimpleNamespace(nodes=depends_on_nodes or []),
    )


@pytest.fixture
def fake_manifest():
    """A manifest with a model, a source, a seed, test nodes and a macro."""
    model_cols = {
        "id": column("id", description="primary\nkey", tags=["pk"]),
        "name": column("name"),
    }
    return SimpleNamespace(
        nodes={
            "model.shop.customers": node(
                "model.shop.customers",
                model_cols,
                schema="analytics",
                relation_name="db.analytics.customers",
                raw_code="select * from {{ ref('stg_customers') }}",
                compiled_code="select id, name from db.raw.stg_customers",
                depends_on_nodes=["model.shop.stg_customers"],
                depends_on_macros=["macro.shop.cents", "macro.dbt.builtin", "macro.shop.missing"],
            ),
            "model.shop.stg_customers": node(
                "model.shop.stg_customers",
                {"id": column("id"), "name": column("name")},
                schema="raw",
                relation_name="db.raw.stg_customers",
                compiled_code="select id, name from db.raw.raw_customers",
                depends_on_nodes=["source.shop.ecom.raw_customers"],
            ),
            "seed.shop.country_codes": node(
                "seed.shop.country_codes", {"code": column("code")}, schema="raw"
            ),
            # A test node must be skipped by the node loop (no test_metadata — legacy shape).
            "test.shop.not_null_customers_id": node(
                "test.shop.not_null_customers_id", schema="analytics"
            ),
            # Proper test nodes: column-level, used by column-tests index tests.
            "test.shop.not_null_customers_id_real": make_test_node(
                test_type="not_null",
                attached_node="model.shop.customers",
                column_name="id",
            ),
            "test.shop.unique_customers_id": make_test_node(
                test_type="unique",
                attached_node="model.shop.customers",
                column_name="id",
            ),
        },
        sources={
            "source.shop.ecom.raw_customers": node(
                "source.shop.ecom.raw_customers",
                {"id": column("id")},
                schema="raw",
                name="raw_customers",
                relation_name="db.raw.raw_customers",
            )
        },
        macros={
            "macro.shop.cents": macro("macro.shop.cents", package_name="shop"),
            "macro.dbt.builtin": macro("macro.dbt.builtin", package_name="dbt"),
        },
        parent_map={
            "model.shop.customers": ["model.shop.stg_customers"],
            "model.shop.stg_customers": ["source.shop.ecom.raw_customers"],
            "source.shop.ecom.raw_customers": [],
            "seed.shop.country_codes": [],
            # A dependency on a test node must be dropped from the graph.
            "test.shop.not_null_customers_id": ["model.shop.customers"],
        },
    )


@pytest.fixture
def fake_catalog():
    """A catalog mirroring the manifest's columns with warehouse types."""
    return SimpleNamespace(
        nodes={
            "model.shop.customers": node(
                "model.shop.customers",
                {"id": column("id", type_="integer"), "name": column("name", type_="text")},
                schema="analytics",
            ),
            "model.shop.stg_customers": node(
                "model.shop.stg_customers",
                {"id": column("id", type_="integer"), "name": column("name", type_="text")},
                schema="raw",
            ),
            "seed.shop.country_codes": node(
                "seed.shop.country_codes", {"code": column("code", type_="text")}, schema="raw"
            ),
        },
        sources={
            "source.shop.ecom.raw_customers": node(
                "source.shop.ecom.raw_customers",
                {"id": column("id", type_="integer")},
                schema="raw",
                name="raw_customers",
            )
        },
    )
