import { FormEvent, useState } from "react";
import { lookupMember } from "../api/client";
import { DebugPanel } from "../components/DebugPanel";
import { MemberCard } from "../components/MemberCard";
import type { MemberLookupResponse } from "../types/brain";

interface MembersPageProps {
  debugMode: boolean;
}

export function MembersPage({ debugMode }: MembersPageProps) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<MemberLookupResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResult(await lookupMember(query.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend chưa sẵn sàng");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid">
      <main className="center-pane form-pane">
        <h2>Member lookup</h2>
        <form className="stack-form" onSubmit={submit}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tên, chức vụ, email, đơn vị..." />
          <button type="submit" disabled={loading || !query.trim()}>
            Tra cứu
          </button>
        </form>
        {error && <div className="error-banner">Backend chưa sẵn sàng: {error}</div>}
        {result?.answer && <div className="answer-block">{result.answer}</div>}
      </main>
      <aside className="right-panel">
        <h2>Member result</h2>
        <div className="metric-row">
          <span>Status</span>
          <strong>{result?.status ?? "-"}</strong>
        </div>
        <div className="metric-row">
          <span>Confidence</span>
          <strong>{result ? Math.round(result.confidence * 100) + "%" : "-"}</strong>
        </div>
        {result?.status === "found" ? <MemberCard member={result.member} /> : null}
        {result?.status === "ambiguous" ? <MemberCard candidates={result.candidates ?? []} /> : null}
        {result?.status === "unknown" ? <div className="muted">Không tìm thấy thành viên phù hợp trong dữ liệu đã nạp.</div> : null}
        {debugMode && <DebugPanel data={result ?? {}} />}
      </aside>
    </div>
  );
}

