import { describe, expect, it } from "vitest";
import {
  applyPositions,
  asLayoutEdges,
  layoutNodes,
  mostConnected,
  radialLayout,
  registerLayout,
  resolveLayout,
} from "@/lib/layout";
import type { Sized } from "@/lib/layout";

const CENTER: Sized = { id: "center", width: 230, height: 100 };
const A: Sized = { id: "a", width: 230, height: 80 };
const B: Sized = { id: "b", width: 230, height: 80 };
const C: Sized = { id: "c", width: 230, height: 80 };
const D: Sized = { id: "d", width: 230, height: 80 };

const EDGES = [
  { source: "center", target: "a" },
  { source: "center", target: "b" },
  { source: "a", target: "c" },
];

describe("radialLayout", () => {
  it("places the center node at the origin (top-left = -width/2, -height/2)", () => {
    const pos = radialLayout("center", [CENTER, A, B], EDGES);
    const p = pos.get("center");
    expect(p).toBeDefined();
    expect(p!.x).toBeCloseTo(-CENTER.width / 2, 0);
    expect(p!.y).toBeCloseTo(-CENTER.height / 2, 0);
  });

  it("assigns ring 0 to center, ring 1 to direct neighbors, ring 2 to 2-hop nodes", () => {
    const pos = radialLayout("center", [CENTER, A, B, C], EDGES);
    const centerPos = pos.get("center")!;
    const aPos = pos.get("a")!;
    const bPos = pos.get("b")!;
    const cPos = pos.get("c")!;

    const centerOf = (p: { x: number; y: number }, s: Sized) =>
      ({ x: p.x + s.width / 2, y: p.y + s.height / 2 });
    const dist = (cx: number, cy: number) => Math.sqrt(cx ** 2 + cy ** 2);

    const cc = centerOf(centerPos, CENTER);
    const ac = centerOf(aPos, A);
    const bc = centerOf(bPos, B);
    const chc = centerOf(cPos, C);

    const dCenter = dist(cc.x, cc.y);
    const dA = dist(ac.x, ac.y);
    const dB = dist(bc.x, bc.y);
    const dC = dist(chc.x, chc.y);

    expect(dCenter).toBeCloseTo(0, 0);
    expect(Math.abs(dA - dB)).toBeLessThan(5);
    expect(dC).toBeGreaterThan(dA);
  });

  it("falls back to dagre layout when centerId is absent from sized", () => {
    const sized = [A, B, C];
    const edges = [{ source: "a", target: "b" }];
    const pos = radialLayout("center", sized, edges);
    expect(pos.has("a")).toBe(true);
    expect(pos.has("b")).toBe(true);
    expect(pos.has("c")).toBe(true);
  });

  it("parks unreachable nodes (no edges) beyond the last ring", () => {
    const pos = radialLayout("center", [CENTER, A, B, D], [
      { source: "center", target: "a" },
      { source: "center", target: "b" },
    ]);
    const dist = (id: string) => {
      const p = pos.get(id)!;
      return Math.sqrt((p.x + CENTER.width / 2) ** 2 + (p.y + CENTER.height / 2) ** 2);
    };
    expect(dist("d")).toBeGreaterThan(dist("a") - 1);
  });

  it("alternating rings are offset (odd-ring angle offset differs from even)", () => {
    const ring1 = radialLayout("center", [CENTER, A], [{ source: "center", target: "a" }]);
    const ring2 = radialLayout("center", [CENTER, A, C], [
      { source: "center", target: "a" },
      { source: "a", target: "c" },
    ]);
    const aP1 = ring1.get("a")!;
    const aP2 = ring2.get("a")!;
    const cP2 = ring2.get("c")!;
    expect(aP1.x).toBeCloseTo(aP2.x, 0);
    expect(cP2).toBeDefined();
  });
});

describe("layoutNodes (dagre)", () => {
  it("assigns positions to all nodes", () => {
    const pos = layoutNodes([CENTER, A, B], [{ source: "center", target: "a" }]);
    expect(pos.has("center")).toBe(true);
    expect(pos.has("a")).toBe(true);
    expect(pos.has("b")).toBe(true);
  });

  it("TB direction stacks nodes vertically: successive x coords are close, y coords spread", () => {
    const chain = [CENTER, A, B, C];
    const edges = [
      { source: "center", target: "a" },
      { source: "a", target: "b" },
      { source: "b", target: "c" },
    ];
    const pos = layoutNodes(chain, edges, "TB");
    const ys = chain.map((s) => pos.get(s.id)!.y);
    const xs = chain.map((s) => pos.get(s.id)!.x);
    const ySpread = Math.max(...ys) - Math.min(...ys);
    const xSpread = Math.max(...xs) - Math.min(...xs);
    expect(ySpread).toBeGreaterThan(xSpread);
  });
});

describe("applyPositions", () => {
  it("merges layout positions back onto React Flow nodes", () => {
    const rfNodes = [
      { id: "center", position: { x: 0, y: 0 }, data: {} },
      { id: "a", position: { x: 0, y: 0 }, data: {} },
    ] as Parameters<typeof applyPositions>[0];
    const pos = new Map([
      ["center", { x: 10, y: 20 }],
      ["a", { x: 30, y: 40 }],
    ]);
    const result = applyPositions(rfNodes, pos);
    expect(result[0].position).toEqual({ x: 10, y: 20 });
    expect(result[1].position).toEqual({ x: 30, y: 40 });
  });

  it("falls back to origin when a node has no position in the map", () => {
    const rfNodes = [{ id: "x", position: { x: 5, y: 5 }, data: {} }] as Parameters<
      typeof applyPositions
    >[0];
    const result = applyPositions(rfNodes, new Map());
    expect(result[0].position).toEqual({ x: 0, y: 0 });
  });
});

describe("asLayoutEdges", () => {
  it("strips extra Edge fields to only source/target", () => {
    const edges = [{ id: "e0", source: "a", target: "b", type: "smoothstep" }] as Parameters<
      typeof asLayoutEdges
    >[0];
    const result = asLayoutEdges(edges);
    expect(result).toEqual([{ source: "a", target: "b" }]);
  });
});

describe("mostConnected", () => {
  it("returns the node touched by the most edges", () => {
    expect(mostConnected([CENTER, A, B, C], EDGES)).toBe("center");
  });

  it("returns null for an empty node list", () => {
    expect(mostConnected([], [])).toBeNull();
  });

  it("falls back to the first node when no edges exist", () => {
    expect(mostConnected([A, B], [])).toBe("a");
  });
});

describe("layout registry", () => {
  it("resolves the built-in dagre and radial engines", () => {
    expect(typeof resolveLayout("dagre")).toBe("function");
    expect(typeof resolveLayout("radial")).toBe("function");
  });

  it("falls back to dagre for an unknown layout name", () => {
    const pos = resolveLayout("does-not-exist")([CENTER, A], [{ source: "center", target: "a" }]);
    expect(pos.has("center")).toBe(true);
    expect(pos.has("a")).toBe(true);
  });

  it("the radial engine centers on the explicit centerId", () => {
    const pos = resolveLayout("radial")([CENTER, A, B], EDGES, { centerId: "center" });
    const c = pos.get("center")!;
    expect(c.x).toBeCloseTo(-CENTER.width / 2, 0);
    expect(c.y).toBeCloseTo(-CENTER.height / 2, 0);
  });

  it("the radial engine auto-centers on the most-connected node when no centerId is given", () => {
    const pos = resolveLayout("radial")([CENTER, A, B, C], EDGES);
    const c = pos.get("center")!;
    expect(c.x).toBeCloseTo(-CENTER.width / 2, 0);
    expect(c.y).toBeCloseTo(-CENTER.height / 2, 0);
  });

  it("a newly registered engine is resolvable by name", () => {
    registerLayout("flat", (sized) => new Map(sized.map((s) => [s.id, { x: 0, y: 0 }])));
    const pos = resolveLayout("flat")([A, B], []);
    expect(pos.get("a")).toEqual({ x: 0, y: 0 });
    expect(pos.get("b")).toEqual({ x: 0, y: 0 });
  });

  it("dagre engine forwards direction=TB: y-spread exceeds x-spread for a linear chain", () => {
    const chain = [CENTER, A, B, C];
    const edges = [
      { source: "center", target: "a" },
      { source: "a", target: "b" },
      { source: "b", target: "c" },
    ];
    const pos = resolveLayout("dagre")(chain, edges, { direction: "TB" });
    const ys = chain.map((s) => pos.get(s.id)!.y);
    const xs = chain.map((s) => pos.get(s.id)!.x);
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(Math.max(...xs) - Math.min(...xs));
  });
});
