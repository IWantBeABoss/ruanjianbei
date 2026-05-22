import type { Conversation, StudentProfile } from "../types";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onCreate: () => void;
  profile: StudentProfile | null;
  onShowProfile: () => void;
  onShowMaterials: () => void;
  onShowExercises: () => void;
  username: string;
  onLogout: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onCreate,
  profile,
  onShowProfile,
  onShowMaterials,
  onShowExercises,
  username,
  onLogout,
}: Props) {
  const filledDimensions = profile
    ? [profile.major_background, profile.knowledge_base, profile.cognitive_style,
       profile.learning_goals, profile.weak_points, profile.schedule_preference,
       profile.content_preference]
        .filter(Boolean).length
    : 0;

  return (
    <aside className="sidebar">
      <div className="sidebar-user">
        <span className="sidebar-user-avatar">{username.charAt(0).toUpperCase()}</span>
        <span className="sidebar-user-name">{username}</span>
        <button className="sidebar-logout" onClick={onLogout} title="Logout">
          &#10140;
        </button>
      </div>
      <button className="new-chat-btn" onClick={onCreate}>
        + New Chat
      </button>
      <ul className="conv-list">
        {conversations.map((c) => (
          <li
            key={c.id}
            className={`conv-item ${c.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="conv-title">{c.title}</span>
            <button
              className="conv-delete"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
              }}
              title="Delete"
            >
              x
            </button>
          </li>
        ))}
      </ul>
      <div className="sidebar-footer">
        <button className="materials-nav-btn" onClick={onShowMaterials}>
          <span>📋</span>
          <span>学习资料</span>
        </button>
        <button className="materials-nav-btn" onClick={onShowExercises}>
          <span>📝</span>
          <span>题目练习</span>
        </button>
        <button className="profile-btn" onClick={onShowProfile}>
          <span>My Profile</span>
          <span className="profile-badge">{filledDimensions}/6</span>
        </button>
      </div>
    </aside>
  );
}
