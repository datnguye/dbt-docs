# Lineage DAG

A node-level lineage graph of your project, built on
[React Flow](https://reactflow.dev/) and shipped as a prebuilt bundle (no build
step at `generate` time).

![lineage DAG](../../assets/img/demo-model-dag.png)

## What it shows

Models, sources, and their `ref` / `source` dependencies — the whole graph, laid
out for you.

- **Pan / zoom / minimap** for navigating large projects.
- **Automatic layout** via [dagre](https://github.com/dagrejs/dagre), so you
  don't hand-place anything.
- **Filter and focus** — isolate a node and its neighborhood.
- **Deep-links** straight to a node, so you can share "look at *this*."

!!! tip "Looking for the ERD?"
    The entity-relationship diagram is documented alongside the catalog — see
    [Catalog & ERD](./catalog.md#the-erd).

## Customizing the graphs (for contributors)

The graph app lives under `frontend/` (React + TypeScript, Vite) and is built
into the committed bundle at `dbdocs/site/bundle/assets/graph/`. `dbdocs
generate` stays pure-Python — it just copies that prebuilt bundle. See the
[Contributing Guide](../development/contributing-guide.md#working-on-the-graph-ui)
for the rebuild commands.
