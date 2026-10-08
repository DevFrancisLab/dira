import { useEffect, useMemo, useState } from "react";
import { Copilot } from "./components/Copilot";
import { Exposure } from "./components/Exposure";
import { LossAnalysis } from "./components/LossAnalysis";
import { Overview } from "./components/Overview";
import { Reports } from "./components/Reports";
import { RiskMap } from "./components/RiskMap";
import { Sidebar } from "./components/Sidebar";
import { mapController } from "./map/controller";
import { loadPortfolio } from "./services/api";

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState("overview");
  const [tier, setTier] = useState("common");
  const [assumption, setAssumption] = useState("reference");
  const [selectedId, setSelectedId] = useState(null);
  const [highlighted, setHighlighted] = useState([]);

  useEffect(() => {
    loadPortfolio().then(setData).catch((reason) => setError(reason.message));
  }, []);

  useEffect(() => {
    mapController.setHandlers({
      setTier,
      setScenario: setAssumption,
      selectBuilding(locId) {
        if (!locId) {
          setSelectedId(null);
          return;
        }
        setHighlighted([]);
        setSelectedId(locId);
        setPage("map");
      },
      highlightBuildings(ids) {
        setSelectedId(null);
        setHighlighted(ids);
        setPage("map");
      },
    });
  }, []);

  const selected = useMemo(() => {
    if (!data || !selectedId) return null;
    return data.buildings.find((building) => building.loc_id === selectedId) || null;
  }, [data, selectedId]);

  if (error) {
    return <div className="boot">Could not load the portfolio. Start the Django API, then refresh. {error}</div>;
  }
  if (!data) {
    return <div className="boot">Loading portfolio from the loss engine…</div>;
  }

  return (
    <div className="shell">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="main">
        <div className={page === "map" ? "map-layer" : "map-layer idle"}>
          <RiskMap
            data={data}
            tier={tier}
            assumption={assumption}
            selectedId={selectedId}
            highlighted={highlighted}
            visible={page === "map"}
          />
        </div>
        {page !== "map" ? (
          <div className="page-layer">
            {page === "overview" ? <Overview data={data} tier={tier} assumption={assumption} /> : null}
            {page === "exposure" ? <Exposure data={data} tier={tier} assumption={assumption} /> : null}
            {page === "loss" ? <LossAnalysis data={data} tier={tier} assumption={assumption} /> : null}
            {page === "reports" ? <Reports data={data} tier={tier} assumption={assumption} /> : null}
          </div>
        ) : null}
        <Copilot
          section={page}
          hidden={page === "reports"}
          data={data}
          tier={tier}
          assumption={assumption}
          selected={selected}
          onOpenMap={() => setPage("map")}
        />
      </main>
    </div>
  );
}
