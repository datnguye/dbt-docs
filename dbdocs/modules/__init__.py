from importlib import import_module


def load_template_module(name: str):
    try:
        return import_module(name=f".{name}", package="dbdocs.modules")
    except ModuleNotFoundError as exc:
        if exc.name == "dbdocs.modules." + name:
            raise Exception(f"Could not find module {name}!")
        raise Exception(f"Failed to load module {name}!")
