export type AppPage = "chat" | "members" | "vision" | "dev";

interface SidebarProps {
  activePage: AppPage;
  onNavigate: (page: AppPage) => void;
  debugMode: boolean;
  onToggleDebug: () => void;
}

const items: Array<{ id: AppPage; label: string }> = [
  { id: "chat", label: "Chat" },
  { id: "members", label: "Members" },
  { id: "vision", label: "Vision" },
  { id: "dev", label: "Dev" }
];

export function Sidebar({ activePage, onNavigate, debugMode, onToggleDebug }: SidebarProps) {
  return (
    <aside className="sidebar">
      <nav>
        {items.map((item) => (
          <button
            key={item.id}
            className={activePage === item.id ? "nav-item active" : "nav-item"}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>
      <label className="debug-toggle">
        <input type="checkbox" checked={debugMode} onChange={onToggleDebug} />
        <span>Debug metadata</span>
      </label>
    </aside>
  );
}

