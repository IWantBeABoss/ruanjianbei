import { useEffect, useRef } from "react";
import type { Message } from "../types";
import MessageItem from "./MessageItem";

interface Props {
  messages: Message[];
  streamingContent: string;
  completed?: boolean;
  totalResources?: number;
  exerciseCount?: number;
  onShowMaterials?: () => void;
  onShowExercises?: () => void;
}

export default function MessageList({ messages, streamingContent, completed, totalResources, exerciseCount, onShowMaterials, onShowExercises }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, completed]);

  return (
    <div className="message-list">
      {messages.map((m) => (
        <MessageItem key={m.id} message={m} />
      ))}
      {streamingContent && (
        <MessageItem
          message={{
            id: "streaming",
            conversation_id: "",
            role: "assistant",
            content: streamingContent,
            created_at: "",
          }}
        />
      )}
      {completed && totalResources && totalResources > 0 && (
        <div className="completion-notice">
          <span>✅ 已为你生成 {totalResources} 个学习资料</span>
          {onShowMaterials && (
            <button className="completion-link" onClick={onShowMaterials}>
              查看学习资料 →
            </button>
          )}
        </div>
      )}
      {completed && exerciseCount && exerciseCount > 0 && (
        <div className="completion-notice">
          <span>📝 已生成 {exerciseCount} 道练习题</span>
          {onShowExercises && (
            <button className="completion-link" onClick={onShowExercises}>
              开始练习 →
            </button>
          )}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
