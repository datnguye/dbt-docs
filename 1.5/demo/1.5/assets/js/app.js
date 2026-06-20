/* dbdocs SPA — entry point.

   Three tiers, one-way dependency (ui → service → data):
     data.js     loads + normalizes the project data dict.
     service.js  pure domain logic over that dict (no DOM).
     ui.js       all DOM rendering.

   This entry is the only place the three meet: load the data, hand it to the
   service tier, then boot the ui. Loaded as a native ES module (no build step).
   The vendored libs (MiniSearch, marked) and the React Flow graph bundle remain
   classic scripts that set globals, which the modules read directly. */

import { loadData } from "./data.js";
import * as svc from "./service.js";
import { boot } from "./ui.js";

loadData().then(function (data) {
  svc.init(data);
  boot();
});
