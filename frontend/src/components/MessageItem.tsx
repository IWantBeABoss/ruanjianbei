import type { Message } from "../types";
import MarkdownView from "./MarkdownView";

interface Props {
  message: Message;
  isStreaming?: string;
}

export default function MessageItem({ message, isStreaming }: Props) {
  const isUser = message.role === "user";
  const content = message.content || isStreaming || "";

  return (
    <div className={`message-row ${isUser ? "user" : "assistant"}`}>
      <div className="message-avatar">{isUser ? "U" : "AI"}</div>
      <div className={`message-bubble ${isUser ? "user" : "assistant"}`}>
        {isUser ? (
          <p>{content}</p>
        ) : (
          <MarkdownView content={content} />
        )}
      </div>
    </div>
  );
}
