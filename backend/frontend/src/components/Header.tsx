import type { HealthResponse } from "../types/brain";
import { HealthBadge } from "./HealthBadge";

interface HeaderProps {
  health: HealthResponse | null;
  loading?: boolean;
}

export function Header({ health, loading }: HeaderProps) {
  return (
    <header className="app-header">
      <div>
        <h1>IVASTBOT</h1>
        <p>Trợ lý AI Viện Vật lý / IOP-VAST</p>
      </div>
      <div className="header-meta">
        {health?.active_model && <span className="model-pill">{health.active_model}</span>}
        <HealthBadge health={health} loading={loading} />
      </div>
    </header>
  );
}

