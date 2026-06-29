import { FormEvent, useEffect, useState } from "react";
import { chat, getApiBaseUrl, getHealth } from "../api/client";
import { DebugPanel } from "../components/DebugPanel";
import { WarningBanner } from "../components/WarningBanner";
import type { BrainResponse, HealthResponse } from "../types/brain";

export function DevPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [raw, setRaw] = useState<unknown>(null);
  const [query, setQuery] = useState("hello");
  const [error, setError] = useState("");

  async function refreshHealth() {
    setError("");
    try {
      const payload = await getHealth();
      setHealth(payload);
      setRaw(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend chưa sẵn sàng");
      setHealth(null);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setError("");
    try {
      const payload: BrainResponse = await chat(query.trim());
      setRaw(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend chưa sẵn sàng");
    }
  }

  useEffect(() => {
    void refreshHealth();
  }, []);

  return (
    <div className="page-grid">
      <main className="center-pane form-pane">
        <h2>Dev console</h2>
        <p className="muted">API base: {getApiBaseUrl()}</p>
        {error && <div className="error-banner">Backend chưa sẵn sàng: {error}</div>}
        <div className="health-grid">
          <div>
            <span>Backend</span>
            <strong>{health?.status ?? "offline"}</strong>
          </div>
          <div>
            <span>Primary</span>
            <strong>{health?.model_primary ?? "-"}</strong>
          </div>
          <div>
            <span>Fallback</span>
            <strong>{health?.model_fallback ?? "-"}</strong>
          </div>
          <div>
            <span>Primary available</span>
            <strong>{String(health?.primary_available ?? false)}</strong>
          </div>
          <div>
            <span>Fallback available</span>
            <strong>{String(health?.fallback_available ?? false)}</strong>
          </div>
          <div>
            <span>Vector DB</span>
            <strong>{health?.vector_db?.sqlite_exists ? "ready" : "missing"}</strong>
          </div>
        </div>
        <WarningBanner warnings={health?.warnings} />
        <button className="secondary-button" type="button" onClick={refreshHealth}>
          Refresh health
        </button>
        <form className="stack-form" onSubmit={submit}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Quick /chat test" />
          <button type="submit">POST /chat</button>
        </form>
      </main>
      <aside className="right-panel wide-pre">
        <DebugPanel data={raw ?? {}} title="Raw JSON response" />
      </aside>
    </div>
  );
}
