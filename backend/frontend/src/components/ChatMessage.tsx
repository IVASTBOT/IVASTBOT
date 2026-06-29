import type { ChatMessageModel } from "../types/brain";
import { WarningBanner } from "./WarningBanner";

interface ChatMessageProps {
  message: ChatMessageModel;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const route = message.response?.route;

  return (
    <article className={`chat-message ${message.role}`}>
      <div className="message-meta">
        <span>{message.role === "user" ? "Bạn" : "IVASTBOT"}</span>
        {route && <span className={`route-chip route-${route}`}>{route}</span>}
      </div>
      <p>{message.text}</p>
      {message.error && <div className="inline-error">{message.error}</div>}
      <WarningBanner warnings={message.response?.warnings} compact />
    </article>
  );
}
