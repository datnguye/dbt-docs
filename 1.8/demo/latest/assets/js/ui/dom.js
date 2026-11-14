/* dbdocs SPA — tier 3 (ui): shared DOM primitives. */

export function el(tag, attrs, children) {
  var node = document.createElement(tag);
  if (attrs) Object.keys(attrs).forEach(function (k) {
    if (k === "class") node.className = attrs[k];
    else if (k === "html") node.innerHTML = attrs[k];
    else if (k === "text") node.textContent = attrs[k];
    else if (k.slice(0, 2) === "on" && typeof attrs[k] === "function") node.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] != null) node.setAttribute(k, attrs[k]);
  });
  (children || []).forEach(function (c) { if (c != null) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
  return node;
}

export function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

export var KNOWN_ICONS = {
  api: 1, catalog: 1, dag: 1, database: 1, info: 1, schema: 1, graph: 1, model: 1, source: 1,
  seed: 1, snapshot: 1, test: 1, unit_test: 1, metric: 1, semantic_model: 1,
  exposure: 1, saved_query: 1, operation: 1, fullscreen: 1, link: 1, health: 1,
};

export function icon(name, size) {
  return el("span", { class: "ic ic--" + name, style: "font-size:" + (size || 16) + "px" });
}
