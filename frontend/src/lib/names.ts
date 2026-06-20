/**
 * The display short-name for a node: the last dot-segment of its unique_id
 * (e.g. `model.shop.orders` → `orders`). Mirrors the shell SPA's `shortName` so
 * the ERD reads the same way as the rest of the site. A record's `label` is
 * sometimes the full unique_id, so the ERD derives the short name itself rather
 * than trusting `label` to be short.
 */
export function shortName(id: string): string {
  const parts = String(id).split(".");
  return parts[parts.length - 1] || String(id);
}
