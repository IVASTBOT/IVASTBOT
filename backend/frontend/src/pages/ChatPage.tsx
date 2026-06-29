import { useState } from "react";
import { chat } from "../api/client";
import { ChatInput } from "../components/ChatInput";
import { ChatWindow } from "../components/ChatWindow";
import { DebugPanel } from "../components/DebugPanel";
import { MemberCard } from "../components/MemberCard";
import { SourcePanel } from "../components/SourcePanel";
import { VisionResult } from "../components/VisionResult";
import { WarningBanner } from "../components/WarningBanner";
import type { BrainResponse, ChatMessageModel, MemberCandidate, MemberRecord, VisionResponse } from "../types/brain";

interface ChatPageProps {
  debugMode: boolean;
  onLastResponse: (response: BrainResponse | null) => void;
}

function getMember(response?: BrainResponse): MemberRecord | null {
  return (response?.metadata?.member as MemberRecord | undefined) ?? null;
}

function getCandidates(response?: BrainResponse): MemberCandidate[] {
  return (response?.metadata?.candidates as MemberCandidate[] | undefined) ?? [];
}

function getVisionResult(response?: BrainResponse): VisionResponse | null {
  if (!response || response.route !== "vision") return null;
  return response.metadata as unknown as VisionResponse;
}

export function ChatPage({ debugMode, onLastResponse }: ChatPageProps) {
  const [messages, setMessages] = useState<ChatMessageModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const lastResponse =
    [...messages].reverse().find((message) => message.role === "assistant" && message.response)?.response ?? null;

  async function sendMessage(text: string) {
    const userMessage: ChatMessageModel = { id: crypto.randomUUID(), role: "user", text };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);
    setError("");
    onLastResponse(null);

    try {
      const response = await chat(text);
      const answer = response.route === "unknown" && !response.answer ? "Hiện chưa có đủ thông tin trong dữ liệu nội bộ." : response.answer;
      const botMessage: ChatMessageModel = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: answer,
        response
      };
      setMessages((current) => [...current, botMessage]);
      onLastResponse(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Backend chưa sẵn sàng";
      setError(message);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", text: "Backend chưa sẵn sàng.", error: message }
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid">
      <main className="center-pane">
        {error && <div className="error-banner">Backend chưa sẵn sàng: {error}</div>}
        <ChatWindow messages={messages} loading={loading} />
        <ChatInput onSubmit={sendMessage} disabled={loading} />
      </main>
      <aside className="right-panel">
        <h2>Response</h2>
        <div className="metric-row">
          <span>Route</span>
          <strong>{lastResponse?.route ?? "-"}</strong>
        </div>
        <div className="metric-row">
          <span>Confidence</span>
          <strong>{lastResponse ? Math.round(lastResponse.confidence * 100) + "%" : "-"}</strong>
        </div>
        <div className="metric-row">
          <span>Type</span>
          <strong>{lastResponse?.confidence_type ?? "-"}</strong>
        </div>
        <WarningBanner warnings={lastResponse?.warnings} />
        <section>
          <h3>Sources</h3>
          <SourcePanel sources={lastResponse?.sources ?? []} />
        </section>
        {lastResponse?.route === "member" && <MemberCard member={getMember(lastResponse)} candidates={getCandidates(lastResponse)} />}
        {lastResponse?.route === "vision" && <VisionResult result={getVisionResult(lastResponse)} />}
        {debugMode && <DebugPanel data={lastResponse?.metadata ?? {}} title="Metadata" />}
      </aside>
    </div>
  );
}
