import { useState } from "react";
import { recognizeVision } from "../api/client";
import { DebugPanel } from "../components/DebugPanel";
import { VisionResult } from "../components/VisionResult";
import { VisionUpload } from "../components/VisionUpload";
import type { VisionResponse } from "../types/brain";

interface VisionPageProps {
  debugMode: boolean;
}

export function VisionPage({ debugMode }: VisionPageProps) {
  const [result, setResult] = useState<VisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function recognize(input: { imagePath?: string; file?: File | null }) {
    setLoading(true);
    setError("");
    try {
      setResult(await recognizeVision(input));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend chưa sẵn sàng");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid">
      <main className="center-pane form-pane">
        <h2>Vision recognition</h2>
        <VisionUpload onRecognize={recognize} loading={loading} />
        {error && <div className="error-banner">Backend chưa sẵn sàng: {error}</div>}
      </main>
      <aside className="right-panel">
        <h2>Vision result</h2>
        <VisionResult result={result} />
        {debugMode && <DebugPanel data={result ?? {}} />}
      </aside>
    </div>
  );
}

