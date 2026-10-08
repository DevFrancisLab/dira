const ITEMS = [
  ["overview", "Overview"],
  ["map", "Risk Map"],
  ["exposure", "Exposure"],
  ["loss", "Loss Analysis"],
  ["reports", "Reports"],
];

export function Sidebar({ page, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">Kenya Re</div>
        <div className="brand-name">CAT Intelligence</div>
      </div>
      <nav>
        {ITEMS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={page === id ? "nav on" : "nav"}
            onClick={() => onNavigate(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <span>Model</span>
        <strong>Reference</strong>
        <span>Synthetic portfolio</span>
      </div>
    </aside>
  );
}
