const BASE = "http://localhost:8000";


function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

// --- Auth ---

export async function login(username: string, password: string) {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail || "Login failed");
  }
  return res.json();
}

export async function register(username: string, password: string) {
  const res = await fetch(`${BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(err.detail || "Registration failed");
  }
  return res.json();
}

export async function getMe() {
  const res = await fetch(`${BASE}/api/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

// --- Conversations ---

export async function createConversation() {
  const res = await fetch(`${BASE}/api/conversations`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function listConversations() {
  const res = await fetch(`${BASE}/api/conversations`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function getConversation(id: string) {
  const res = await fetch(`${BASE}/api/conversations/${id}`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function deleteConversation(id: string) {
  const res = await fetch(`${BASE}/api/conversations/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function getStudentProfile() {
  const res = await fetch(`${BASE}/api/student/profile`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function extractProfile(conversationId: string) {
  const res = await fetch(`${BASE}/api/student/profile/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  return res.json();
}

export async function listMaterials() {
  const res = await fetch(`${BASE}/api/materials`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function listExercises() {
  const res = await fetch(`${BASE}/api/exercises`, {
    headers: getAuthHeaders(),
  });
  return res.json();
}

export async function listResources(conversationId?: string) {
  const url = conversationId
    ? `${BASE}/api/resources?conversation_id=${conversationId}`
    : `${BASE}/api/resources/all`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  return res.json();
}

export function getResourceDownloadUrl(resourceId: string): string {
  return `${BASE}/api/resources/${resourceId}/download`;
}

export async function downloadResource(resourceId: string, fileName: string) {
  const res = await fetch(getResourceDownloadUrl(resourceId), {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function chatWithStream(
  convId: string,
  content: string,
  onDelta: (delta: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
  onStatus?: (status: string) => void,
  onProgress?: (current: number, total: number, label: string, resourceType: string) => void,
  onComplete?: (total: number, quizTotal: number) => void,
  signal?: AbortSignal
) {
  const res = await fetch(`${BASE}/api/conversations/${convId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ content }),
    signal,
  });

  if (!res.ok) {
    onError(`HTTP ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          onDone();
          return;
        }
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === "status" && parsed.status && onStatus) {
            onStatus(parsed.status);
            continue;
          }
          if (parsed.type === "progress" && onProgress) {
            onProgress(parsed.current, parsed.total, parsed.label, parsed.resource_type);
            continue;
          }
          if (parsed.type === "complete" && onComplete) {
            onComplete(parsed.total, parsed.quiz_total || 0);
            continue;
          }
          if (parsed.error) {
            onError(parsed.error);
            return;
          }
          // Skip hidden deltas (quiz JSON — not rendered in chat)
          if (parsed.hidden) continue;
          if (parsed.delta) onDelta(parsed.delta);
        } catch {
          // ignore parse errors for partial chunks
        }
      }
    }
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      return; // stream was intentionally cancelled, not an error
    }
    onError(e instanceof Error ? e.message : "Stream error");
  } finally {
    reader.cancel().catch(() => {});
  }
}
