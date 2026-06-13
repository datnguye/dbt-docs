from click.testing import CliRunner

import dbdocs.cli.main as cli_main
from dbdocs.cli.main import dbdocs
from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DbDocsConfigError, DeployError, LineageError
from dbdocs.main import main


def test_version_flag_reports_version():
    result = CliRunner().invoke(dbdocs, ["--version"])
    assert result.exit_code == 0
    assert cli_main.__version__ in result.output


def test_no_args_shows_help():
    result = CliRunner().invoke(dbdocs, [])
    assert result.exit_code != 0
    assert "Usage" in result.output
    assert "generate" in result.output


def test_generate_builds_site(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        cli_main.ReportBuilder,
        "generate",
        lambda self, output_dir: seen.setdefault("out", output_dir) or "/site",
    )
    result = CliRunner().invoke(dbdocs, ["generate"])
    assert result.exit_code == 0
    # The build was invoked; the builder itself logs the "Generated site at ..."
    # line, so the CLI no longer echoes a duplicate.
    assert "out" in seen


def test_generate_dialect_override(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        cli_main.ReportBuilder,
        "generate",
        lambda self, output_dir: seen.setdefault("dialect", self.config.dialect) or "/site",
    )
    result = CliRunner().invoke(dbdocs, ["generate", "--dialect", "bigquery"])
    assert result.exit_code == 0
    assert seen["dialect"] == "bigquery"


def test_generate_run_results_override(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        cli_main.ReportBuilder,
        "generate",
        lambda self, output_dir: seen.setdefault("run_results", self.config.run_results) or "/site",
    )
    result = CliRunner().invoke(dbdocs, ["generate", "--run-results", "/custom/run_results.json"])
    assert result.exit_code == 0
    assert seen["run_results"] == "/custom/run_results.json"


def test_generate_output_dir_override(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        cli_main.ReportBuilder,
        "generate",
        lambda self, output_dir: seen.setdefault("out", output_dir) or "/x",
    )
    result = CliRunner().invoke(dbdocs, ["generate", "-o", "/custom"])
    assert result.exit_code == 0
    assert seen["out"] == "/custom"


def test_generate_dbdocs_error_is_clean(monkeypatch):
    def _boom(self, output_dir):
        raise LineageError("kaboom")

    monkeypatch.setattr(cli_main.ReportBuilder, "generate", _boom)
    result = CliRunner().invoke(dbdocs, ["generate"])
    assert result.exit_code != 0
    assert "kaboom" in result.output


def test_serve_command(monkeypatch):
    served = {}

    class _FakeServer:
        def __init__(self, addr, handler):
            served["addr"] = addr

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def serve_forever(self):
            served["served"] = True

    monkeypatch.setattr(cli_main.socketserver, "ThreadingTCPServer", _FakeServer)
    result = CliRunner().invoke(dbdocs, ["serve", "--port", "9001"])
    assert result.exit_code == 0
    assert served["addr"] == ("127.0.0.1", 9001)
    assert served["served"] is True


def test_serve_suppresses_version_banner(monkeypatch):
    """`serve` is a long-running command — it should not log the version banner."""
    msgs = []
    monkeypatch.setattr(cli_main.logger, "info", lambda m, *a: msgs.append(m % a))
    monkeypatch.setattr(
        cli_main.socketserver,
        "ThreadingTCPServer",
        type(
            "_S",
            (),
            {
                "__init__": lambda self, addr, handler: None,
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: False,
                "serve_forever": lambda self: None,
            },
        ),
    )
    CliRunner().invoke(dbdocs, ["serve"])
    assert not any("Run with dbdocs" in m for m in msgs)


def test_generate_logs_version_banner(monkeypatch):
    """Build commands keep the version banner (it records the build version)."""
    msgs = []
    monkeypatch.setattr(cli_main.logger, "info", lambda m, *a: msgs.append(m % a))
    monkeypatch.setattr(cli_main.ReportBuilder, "generate", lambda self, output_dir: "/site")
    CliRunner().invoke(dbdocs, ["generate"])
    assert any("Run with dbdocs" in m for m in msgs)


def test_deploy_command(monkeypatch):
    seen = {}

    def _deploy(config, version, alias, push, title):
        seen.update(version=version, alias=alias, push=push, title=title)
        return "/site/1.2"

    monkeypatch.setattr(cli_main.deploy_module, "deploy", _deploy)
    result = CliRunner().invoke(
        dbdocs, ["deploy", "--version", "1.2", "--alias", "latest", "--title", "v1.2", "--push"]
    )
    assert result.exit_code == 0
    assert seen == {"version": "1.2", "alias": "latest", "push": True, "title": "v1.2"}
    assert "Deployed version 1.2" in result.output


def test_deploy_delete_command(monkeypatch):
    seen = {}

    def _delete(config, version, push):
        seen.update(version=version, push=push)

    monkeypatch.setattr(cli_main.deploy_module, "delete", _delete)
    result = CliRunner().invoke(dbdocs, ["deploy", "--version", "1.0", "--delete"])
    assert result.exit_code == 0
    assert seen == {"version": "1.0", "push": False}
    assert "Deleted version 1.0" in result.output


def test_deploy_dbdocs_error_is_clean(monkeypatch):
    def _boom(config, version, alias, push, title):
        raise DeployError("push failed")

    monkeypatch.setattr(cli_main.deploy_module, "deploy", _boom)
    result = CliRunner().invoke(dbdocs, ["deploy", "--version", "1.0"])
    assert result.exit_code != 0
    assert "push failed" in result.output


def test_config_error_is_clean_error(monkeypatch):
    def _boom(path):
        raise DbDocsConfigError("bad yaml")

    monkeypatch.setattr(cli_main.DbDocsConfig, "load", staticmethod(_boom))
    result = CliRunner().invoke(dbdocs, ["generate"])
    assert result.exit_code != 0
    assert "bad yaml" in result.output


def test_group_config_option_flows_to_subcommand(monkeypatch, tmp_path):
    cfg_file = tmp_path / "dbdocs.yml"
    cfg_file.write_text("site_name: From File\n", encoding="utf-8")

    seen = {}
    monkeypatch.setattr(
        cli_main.ReportBuilder,
        "generate",
        lambda self, output_dir: seen.setdefault("config", self.config) or "/s",
    )
    result = CliRunner().invoke(dbdocs, ["--config", str(cfg_file), "generate"])
    assert result.exit_code == 0
    assert isinstance(seen["config"], DbDocsConfig)
    assert seen["config"].site_name == "From File"


def test_main_entrypoint_invokes_cli(monkeypatch):
    called = []
    monkeypatch.setattr("dbdocs.main.cli.dbdocs", lambda: called.append(True))
    main()
    assert called == [True]
