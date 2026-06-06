import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { GraphApp } from "./GraphApp";
import type { DbdocsData, GraphMode } from "./types";
import "@xyflow/react/dist/style.css";
import "./graph.css";

// The vanilla SPA owns navigation; this bundle only renders graphs. It mounts a
// React root into an element the SPA creates, reading the mode/focus from the
// element's dataset and the project data from window.dbdocsData.

const roots = new WeakMap<HTMLElement, Root>();

function mount(el: HTMLElement): void {
  const data = (window as unknown as { dbdocsData?: DbdocsData }).dbdocsData;
  if (!data) return;
  const mode = (el.dataset.mode as GraphMode) || "dag";
  const focus = el.dataset.focus || null;
  const onOpenNode = (id: string) => {
    location.hash = `#/node/${encodeURIComponent(id)}`;
  };
  const root = createRoot(el);
  roots.set(el, root);
  root.render(
    <StrictMode>
      <GraphApp mode={mode} focus={focus} data={data} onOpenNode={onOpenNode} />
    </StrictMode>,
  );
}

function unmount(el: HTMLElement): void {
  const root = roots.get(el);
  if (root) {
    root.unmount();
    roots.delete(el);
  }
}

(window as unknown as { dbdocsGraph: unknown }).dbdocsGraph = { mount, unmount };
