import functools
import importlib.metadata
import socketserver
from http.server import SimpleHTTPRequestHandler

import click

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DbDocsError
from dbdocs.core.log import logger
from dbdocs.site import deploy as deploy_module
from dbdocs.site.builder import ReportBuilder

__version__ = importlib.metadata.version("dbdocs")


# dbdocs
@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    no_args_is_help=True,
    epilog="Specify one of these sub-commands and you can find more help from there.",
)
@click.version_option(__version__)
@click.option("-c", "--config", "config_path", default=None, help="Path to dbdocs.yml.")
@click.pass_context
def dbdocs(ctx, config_path):
    """Alternative dbt docs site: dbt docs + ERD + column-level lineage."""
    # The version banner is useful for the build commands (generate/deploy) but
    # is noise for the long-running `serve`, which prints its own start line.
    if ctx.invoked_subcommand != "serve":
        logger.info("Run with dbdocs==%s", __version__)
    try:
        ctx.obj = DbDocsConfig.load(config_path)
    except DbDocsError as exc:
        raise click.ClickException(str(exc)) from exc


@dbdocs.command(name="generate")
@click.option("-o", "--output-dir", default=None, help="Where to write the site (default: config).")
@click.option(
    "--dialect", default=None, help="SQL dialect for column lineage (default: adapter_type)."
)
@click.option(
    "--run-results",
    default=None,
    help=(
        "Path to run_results.json for the Health Check (default: <target_dir>/run_results.json)."
    ),
)
@click.pass_obj
def generate(config: DbDocsConfig, output_dir, dialect, run_results):
    """Build the site from dbt artifacts (served over HTTP; data loaded externally)."""
    if dialect is not None:
        config.dialect = dialect
    if run_results is not None:
        config.run_results = run_results
    try:
        ReportBuilder(config).generate(output_dir=output_dir)
    except DbDocsError as exc:
        raise click.ClickException(str(exc)) from exc
    # The builder already logs "Generated site at <path> (N nodes, M edges)".


@dbdocs.command(name="serve")
@click.option("-p", "--port", default=8000, show_default=True, help="Port to serve on.")
@click.pass_obj
def serve(config: DbDocsConfig, port):
    """Serve the generated site locally (static http server)."""
    handler = functools.partial(SimpleHTTPRequestHandler, directory=config.output_path)
    click.echo(f"Serving {config.output_path} at http://127.0.0.1:{port} (Ctrl-C to stop)")
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as httpd:
        httpd.serve_forever()


@dbdocs.command(name="deploy")
@click.option("--version", "version", required=True, help="Version label to deploy (e.g. 1.2).")
@click.option("--alias", default=None, help="Moving alias for this version (e.g. latest).")
@click.option(
    "--title", default=None, help="Display title for this version (default: the version)."
)
@click.option(
    "--delete", "delete", is_flag=True, default=False, help="Delete this version instead."
)
@click.option("--push/--no-push", default=False, help="Publish to the gh-pages branch.")
@click.pass_obj
def deploy(config: DbDocsConfig, version, alias, title, delete, push):
    """Generate a versioned build and update the version index (or --delete one)."""
    try:
        if delete:
            deploy_module.delete(config, version=version, push=push)
            click.echo(f"Deleted version {version}")
            return
        out = deploy_module.deploy(config, version=version, alias=alias, push=push, title=title)
    except DbDocsError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Deployed version {version} into {out}")
