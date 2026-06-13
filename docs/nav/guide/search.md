# Full-text Search

Every generated dbdocs site has a full-text search box in the top bar. It runs
entirely in your browser — no backend, no index server, no network round-trip.
Start typing and matches appear instantly.

## What it searches

A query matches across the whole searchable surface of every node, not just its
name:

- **Names** — the model/source/seed name and its display label.
- **Columns** — column names *and* their descriptions.
- **Tags** — any dbt tags on the node.
- **Description** — the node's documented description.
- **Relation** — the warehouse `database.schema.table` it lands in.
- **Package** — the dbt package the node belongs to.
- **Macros** — the names of macros a model calls.
- **SQL** — the raw and compiled SQL body, so a query can land on a table
  reference or a macro call buried deep in a model.

So searching `unique` finds the models whose SQL mentions it; searching a column
name finds the models that expose that column, even when the column name is
nothing like the model name.

## Why a result matched

Because the index is wide, dbdocs shows you *why* each result is there. When a
match comes from something other than the name, the result row carries a small
snippet — a labelled chip (`Column`, `SQL`, `Tag`, …) plus an excerpt of the
matching text with your search terms highlighted. No more staring at a wall of
model names wondering which one actually matched.

Name matches rank above incidental SQL-body matches, so the model you were
actually looking for stays at the top.

## Filters

Two inline filters let you narrow a search without leaving the box:

| Filter | What it does | Example |
|--------|--------------|---------|
| `type:` | Restrict results to one resource type | `type:model`, `type:source`, `type:seed` |
| `label:` (or `name:`) | Match the **name** only — skips the SQL/description noise | `label:stg` |

Filters combine with the rest of your query:

- `type:model orders` — models whose text matches *orders*.
- `type:seed` — every seed, on its own (no free text needed).
- `label:stg` — nodes whose **name** contains *stg*, ignoring any model that
  merely references a staging table in its SQL.

!!! tip "Filter by type when the catalog is big"
    On a large project, `type:model my_thing` is the fastest way to cut through
    the sources, seeds, and tests that happen to share a word with what you want.

## Notes

- Search is **case-insensitive** and does light **prefix + fuzzy** matching on
  names, columns, and tags — so a half-typed or slightly-misspelled name still
  hits. The bulkier text (descriptions, SQL) matches on whole words only, to keep
  a common keyword from flooding every result.
- On very large projects (thousands of models) the SQL body is dropped from the
  index to keep the browser snappy; name, column, tag, and macro search stay put.
- A query that matches nothing says so — an empty box is just an empty box, but a
  real query with no hits tells you plainly.
- The dropdown is **fully keyboard-operable**: ↑/↓ move through the results,
  <kbd>Enter</kbd> opens the highlighted one, and <kbd>Esc</kbd> dismisses it —
  no reach for the mouse required. It's wired as an ARIA combobox/listbox, so
  screen readers announce results as you type.
