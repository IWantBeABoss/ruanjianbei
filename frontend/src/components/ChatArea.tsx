import type { Message } from "../types";
import type { ProgressEvent } from "../types";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import MaterialsPanel from "./MaterialsPanel";
import ExercisePanel from "./ExercisePanel";
import ProgressBar from "./ProgressBar";

interface Props {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  onSend: (content: string) => void;
  active: boolean;
  error: string | null;
  agentStatus: string | null;
  onSelectConversation: (id: string) => void;
  showPanel: "materials" | "exercises" | null;
  progress: ProgressEvent | null;
  completed: boolean;
  totalResources: number;
  exerciseCount: number;
  onShowMaterials: () => void;
  onShowExercises: () => void;
}

export default function ChatArea({
  messages,
  streamingContent,
  isStreaming,
  onSend,
  active,
  error,
  agentStatus,
  onSelectConversation,
  showPanel,
  progress,
  completed,
  totalResources,
  exerciseCount,
  onShowMaterials,
  onShowExercises,
}: Props) {
  if (!active) {
    if (showPanel === "exercises") {
      return (
        <div className="chat-area">
          <ExercisePanel onSelectConversation={onSelectConversation} />
        </div>
      );
    }
    if (showPanel === "materials") {
      return (
        <div className="chat-area">
          <div className="ex-panel-header">📋 学习资料</div>
          <MaterialsPanel onSelectConversation={onSelectConversation} />
        </div>
      );
    }
    return (
      <div className="chat-area empty-chat">
        <div className="empty-chat-top">
          <h1>AI 学习助手</h1>
          <p>新建一个对话或从侧边栏选择历史记录</p>
        </div>
        <MaterialsPanel onSelectConversation={onSelectConversation} />
      </div>
    );
  }

  return (
    <div className="chat-area">
      <MessageList
        messages={messages}
        streamingContent={streamingContent}
        completed={completed}
        totalResources={totalResources}
        exerciseCount={exerciseCount}
        onShowMaterials={onShowMaterials}
        onShowExercises={onShowExercises}
      />
      {progress && (
        <ProgressBar
          current={progress.current}
          total={progress.total}
          label={progress.label}
        />
      )}
      {agentStatus && (
        <div className="agent-status">
          <span className="agent-status-spinner" />
          {agentStatus}
        </div>
      )}
      {error && <div className="chat-error">Error: {error}</div>}
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
