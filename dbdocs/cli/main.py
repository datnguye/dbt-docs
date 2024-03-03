import importlib.metadata

import click

from dbdocs.helpers.log import logger
from dbdocs.modules import load_template_module

__version__ = importlib.metadata.version("dbdocs")


# dbdocs
@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    no_args_is_help=True,
    epilog="Specify one of these sub-commands and you can find more help from there.",
)
@click.version_option(__version__)
@click.pass_context
def dbdocs(ctx, **kwargs):
    """Auto-generated data documentation site for dbt projects"""
    logger.info(f"Run with dbdocs=={__version__}")


# dbtdocs run
@dbdocs.command(name="generate")
@click.pass_context
def generate(ctx, **kwargs):
    """
    Generate static sites
    """
    module = load_template_module(name="standard")  # TODO
    module.generate()
