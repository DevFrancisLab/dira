import { mapController } from "../map/controller";

const PAGE_KEYS = [
  ["reports", ["reports", "report"]],
  ["overview", ["overview", "home"]],
  ["exposure", ["exposure"]],
  ["loss", ["loss analysis", "loss section"]],
  ["map", ["risk map", "the map", "map"]],
];

function hasWord(text, phrase) {
  const pattern = new RegExp(`\\b${phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`);
  return pattern.test(text);
}

export function isRiskBrief(message) {
  const text = String(message || "").toLowerCase().replace(/\s+/g, " ").trim();
  return /\b(highest[-\s]?risk|most at risk)\b/.test(text) && /\bextreme\b/.test(text);
}

const TIERS = ["extreme", "severe", "moderate", "occasional", "common"];
const SCENARIOS = ["reference", "low", "high", "reference_rcc80"];

export function commandActions(message, hotspots) {
  if (isRiskBrief(message)) return [];
  const text = message.toLowerCase().replace(/\s+/g, " ").trim();
  const actions = [];
  if (/\b(go to|open|show|take me|switch to|navigate)\b/.test(text)) {
    for (const [page, keys] of PAGE_KEYS) {
      if (keys.some((key) => hasWord(text, key))) {
        actions.push({ name: "navigate", page });
        break;
      }
    }
  }
  const hotspot = [...(hotspots || [])]
    .sort((left, right) => right.name.length - left.name.length)
    .find((item) => hasWord(text, item.name.toLowerCase()));
  if (hotspot) {
    if (!actions.some((item) => item.page === "map")) actions.push({ name: "navigate", page: "map" });
    actions.push({ name: "fly_to", hotspot: hotspot.name });
  } else if (/\bzoom in(?:to)?\b/.test(text)) {
    if (!actions.some((item) => item.page === "map")) actions.push({ name: "navigate", page: "map" });
    actions.push({ name: "zoom_in" });
  } else if (/\bzoom out\b/.test(text)) {
    if (!actions.some((item) => item.page === "map")) actions.push({ name: "navigate", page: "map" });
    actions.push({ name: "zoom_out" });
  }
  return actions;
}

const PAGE_LABEL = {
  overview: "Overview",
  map: "Risk Map",
  exposure: "Exposure",
  loss: "Loss Analysis",
  reports: "Reports",
};

export function describeActions(actions) {
  const parts = [];
  for (const action of actions || []) {
    if (action.name === "navigate") parts.push(`Opened ${PAGE_LABEL[action.page]}.`);
    else if (action.name === "zoom_in") parts.push("Zoomed in on the map.");
    else if (action.name === "zoom_out") parts.push("Zoomed out on the map.");
    else if (action.name === "fly_to") parts.push(`Moved the map to ${action.hotspot}.`);
  }
  return parts.join(" ");
}

export function applyCopilotActions(actions, { onNavigate, hotspots }) {
  for (const action of actions || []) {
    if (!action || typeof action.name !== "string") continue;
    if (action.name === "navigate" && PAGE_KEYS.some(([page]) => page === action.page)) {
      onNavigate(action.page);
    } else if (action.name === "zoom_in") {
      onNavigate("map");
      window.setTimeout(() => mapController.zoomIn(), 50);
    } else if (action.name === "zoom_out") {
      onNavigate("map");
      window.setTimeout(() => mapController.zoomOut(), 50);
    } else if (action.name === "fly_to") {
      const hotspot = (hotspots || []).find(
        (item) => item.name.toLowerCase() === String(action.hotspot || "").toLowerCase(),
      );
      if (!hotspot) continue;
      onNavigate("map");
      window.setTimeout(() => mapController.flyTo(hotspot.lat, hotspot.lon, 14), 50);
    } else if (action.name === "set_tier" && TIERS.includes(action.tier)) {
      mapController.setTier(action.tier);
    } else if (action.name === "set_scenario" && SCENARIOS.includes(action.scenario)) {
      mapController.setScenario(action.scenario);
    } else if (action.name === "highlight" && Array.isArray(action.ids)) {
      const ids = action.ids.filter((id) => typeof id === "string" && id);
      if (ids.length) mapController.highlightBuildings(ids);
    }
  }
}
