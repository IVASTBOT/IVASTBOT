import type { HealthResponse } from "../types/brain";

interface HealthBadgeProps {
  health: HealthResponse | null;
  loading?: boolean;
}

export function HealthBadge({ health, loading }: HealthBadgeProps) {
  const online = health?.status === "ok";
  const label = loading ? "checking" : online ? "online" : "offline";

  return (
    <div className={`health-badge ${online ? "online" : "offline"}`}>
      <span className="status-dot" />
      <span>{label}</span>
    </div>
  );
}

