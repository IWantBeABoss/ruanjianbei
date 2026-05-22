import { useEffect, useState } from "react";
import { useAuthStore } from "./hooks/useAuth";
import { useChatStore } from "./hooks/useConversations";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import "./App.css";

export default function App() {
  const { isAuthenticated, isLoading, user, checkAuth, logout } = useAuthStore();
  const {
    conversations,
    activeId,
    messages,
    streamingContent,
    isStreaming,
    error,
    profile,
    agentStatus,
    progress,
    completed,
    totalResources,
    exerciseCount,
    loadConversations,
    createConversation,
    deleteConversation,
    setActive,
    sendMessage,
    loadProfile,
    showProfile,
  } = useChatStore();

  const [showPanel, setShowPanel] = useState<"materials" | "exercises" | null>(null);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
      loadProfile();
    }
  }, [isAuthenticated, loadConversations, loadProfile]);

  const handleShowMaterials = () => {
    const state = useChatStore.getState();
    if (state._abortController) state._abortController.abort();
    useChatStore.setState({
      activeId: null, messages: [], streamingContent: "",
      isStreaming: false, agentStatus: null,
      _abortController: null, _streamingConvId: null,
    });
    setShowPanel("materials");
  };

  const handleShowExercises = () => {
    const state = useChatStore.getState();
    if (state._abortController) state._abortController.abort();
    useChatStore.setState({
      activeId: null, messages: [], streamingContent: "",
      isStreaming: false, agentStatus: null,
      _abortController: null, _streamingConvId: null,
    });
    setShowPanel("exercises");
  };

  const handleSelectConversation = (id: string) => {
    setShowPanel(null);
    setActive(id);
  };

  if (isLoading) {
    return (
      <div className="app-loading">
        <div className="auth-spinner" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return (
    <div className="app-layout">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelectConversation}
        onDelete={deleteConversation}
        onCreate={() => { setShowPanel(null); createConversation(); }}
        profile={profile}
        onShowProfile={showProfile}
        onShowMaterials={handleShowMaterials}
        onShowExercises={handleShowExercises}
        username={user?.username ?? ""}
        onLogout={logout}
      />
      <ChatArea
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
        onSend={sendMessage}
        active={activeId !== null}
        error={error}
        agentStatus={agentStatus}
        onSelectConversation={handleSelectConversation}
        showPanel={showPanel}
        progress={progress}
        completed={completed}
        totalResources={totalResources}
        exerciseCount={exerciseCount}
        onShowMaterials={handleShowMaterials}
        onShowExercises={handleShowExercises}
      />
    </div>
  );
}
