import { useState, useEffect } from "react";
import type { Resource } from "../types";
import * as api from "../api/chat";
import MarkdownView from "./MarkdownView";

interface Props {
  onSelectConversation: (id: string) => void;
}

const TYPE_ICONS: Record<string, string> = {
  document: "📄", quiz: "📝", mindmap: "🧠",
  video: "🎬", code: "💻", reading: "📚",
  path: "🗺️", tutor: "💡", assessment: "📊",
};

const TYPE_LABELS: Record<string, string> = {
  document: "课程讲解文档", quiz: "配套练习题",
  mindmap: "知识点思维导图", video: "教学视频脚本",
  code: "代码实操案例", reading: "拓展阅读材料",
  path: "学习路径规划", tutor: "答疑辅导",
  assessment: "学习效果评估",
};

function formatSize(content: string): string {
  const bytes = new TextEncoder().encode(content).length;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export default function MaterialsPanel({ onSelectConversation }: Props) {
  const [grouped, setGrouped] = useState<Record<string, Resource[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const fetchResources = () => {
    setLoading(true);
    setError(null);
    api.listResources().then((data) => {
      setGrouped(data || {});
      setLoading(false);
    }).catch((e) => {
      console.error("[MaterialsPanel] Fetch error:", e);
      setError(String(e));
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchResources();
  }, []);

  const handleDownload = async (e: React.MouseEvent, r: Resource) => {
    e.stopPropagation();
    setDownloadingId(r.id);
    try {
      await api.downloadResource(r.id, r.file_name || `${r.topic}.md`);
    } catch (err) {
      console.error("Download failed:", err);
    }
    setDownloadingId(null);
  };

  if (loading) {
    return (
      <div className="materials-panel">
        <div className="materials-loading">加载中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="materials-panel">
        <div className="ex-empty">
          <p>加载失败</p>
          <p className="ex-empty-hint">{error}</p>
        </div>
      </div>
    );
  }

  const entries = Object.entries(grouped);
  if (entries.length === 0) {
    return (
      <div className="materials-panel">
        <div className="ex-empty">
          <p>暂无学习资料</p>
          <p className="ex-empty-hint">使用学习模式对话，生成的资料将以文件形式保存在这里</p>
        </div>
      </div>
    );
  }

  return (
    <div className="materials-panel">
      <div className="materials-file-list">
        {entries.map(([convId, resources]) =>
          resources.map((r) => {
            const isExpanded = expandedId === String(r.id);
            const icon = TYPE_ICONS[r.resource_type] || "📎";
            const label = TYPE_LABELS[r.resource_type] || r.resource_type;

            return (
              <div key={r.id} className={`material-file-card ${isExpanded ? "expanded" : ""}`}>
                <div className="file-card-main">
                  <div
                    className="file-card-header"
                    onClick={() => setExpandedId(isExpanded ? null : String(r.id))}
                  >
                    <span className="file-card-icon">{icon}</span>
                    <div className="file-card-info">
                      <div className="file-card-name">{r.file_name || `${r.topic}.md`}</div>
                      <div className="file-card-meta">
                        <span>{label}</span>
                        <span>·</span>
                        <span>{formatSize(r.content)}</span>
                        <span>·</span>
                        <span>{formatDate(r.created_at)}</span>
                        {r.reviewed && <span className="file-badge-reviewed">已审核</span>}
                      </div>
                    </div>
                    <span className="file-card-expand">{isExpanded ? "▲" : "▼"}</span>
                  </div>

                  <div className="file-card-actions">
                    <button
                      className="file-download-btn"
                      onClick={(e) => handleDownload(e, r)}
                      disabled={downloadingId === r.id}
                    >
                      {downloadingId === r.id ? "⏳ 下载中..." : "⬇ 下载"}
                    </button>
                    <button
                      className="file-source-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectConversation(r.conversation_id);
                      }}
                    >
                      💬 对话
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="file-card-preview">
                    <MarkdownView content={r.content} />
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
