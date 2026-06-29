import type { ChatMessageModel } from "../types/brain";
import { ChatMessage } from "./ChatMessage";

interface ChatWindowProps {
  messages: ChatMessageModel[];
  loading: boolean;
}

export function ChatWindow({ messages, loading }: ChatWindowProps) {
  return (
    <section className="chat-window">
      {messages.length === 0 ? (
        <div className="empty-state">
          <h2>AI receptionist cho IOP-VAST</h2>
          <p>Hỏi về thời gian, nhân sự, thông tin trung tâm, hoặc dữ liệu RAG nội bộ.</p>
        </div>
      ) : (
        messages.map((message) => <ChatMessage key={message.id} message={message} />)
      )}
      {loading && <div className="typing">Đang xử lý...</div>}
    </section>
  );
}

