// import { create } from "zustand";
// import type { Conversation, Message, StudentProfile } from "../types";
// import * as api from "../api/chat";
//
// interface ChatState {
//   conversations: Conversation[];
//   activeId: string | null;
//   messages: Message[];
//   streamingContent: string;
//   isStreaming: boolean;
//   error: string | null;
//   profile: StudentProfile | null;
//   agentStatus: string | null;
//   _abortController: AbortController | null;
//   _streamingConvId: string | null;
//
//   loadConversations: () => Promise<void>;
//   createConversation: () => Promise<void>;
//   deleteConversation: (id: string) => Promise<void>;
//   setActive: (id: string) => Promise<void>;
//   sendMessage: (content: string) => Promise<void>;
//   loadProfile: () => Promise<void>;
//   showProfile: () => Promise<void>;
// }
//
// function _abortActiveStream(get: () => ChatState) {
//   const { _abortController } = get();
//   if (_abortController) {
//     _abortController.abort();
//   }
// }
//
// export const useChatStore = create<ChatState>((set, get) => ({
//   conversations: [],
//   activeId: null,
//   messages: [],
//   streamingContent: "",
//   isStreaming: false,
//   error: null,
//   profile: null,
//   agentStatus: null,
//   _abortController: null,
//   _streamingConvId: null,
//
//   loadConversations: async () => {
//     const data = await api.listConversations();
//     set({ conversations: data });
//   },
//
//   createConversation: async () => {
//     _abortActiveStream(get);
//     const conv = await api.createConversation();
//     set({
//       conversations: [conv, ...get().conversations],
//       activeId: conv.id,
//       messages: [],
//       streamingContent: "",
//       isStreaming: false,
//       error: null,
//       agentStatus: null,
//       _abortController: null,
//       _streamingConvId: null,
//     });
//   },
//
//   deleteConversation: async (id) => {
//     await api.deleteConversation(id);
//     set((s) => {
//       const filtered = s.conversations.filter((c) => c.id !== id);
//       if (s.activeId === id) {
//         _abortActiveStream(get);
//         return {
//           conversations: filtered,
//           activeId: null,
//           messages: [],
//           streamingContent: "",
//           isStreaming: false,
//           agentStatus: null,
//           _abortController: null,
//           _streamingConvId: null,
//         };
//       }
//       return { conversations: filtered };
//     });
//   },
//
//   setActive: async (id) => {
//     _abortActiveStream(get);
//     const conv = await api.getConversation(id);
//     set({
//       activeId: id,
//       messages: conv.messages || [],
//       streamingContent: "",
//       isStreaming: false,
//       error: null,
//       agentStatus: null,
//       _abortController: null,
//       _streamingConvId: null,
//     });
//   },
//
//   sendMessage: async (content) => {
//     const { activeId, messages } = get();
//     if (!activeId || !content.trim()) return;
//
//     // Abort any previous stream (shouldn't normally happen, but safe)
//     _abortActiveStream(get);
//
//     const abortController = new AbortController();
//     const streamingConvId = activeId;
//
//     const userMsg: Message = {
//       id: crypto.randomUUID(),
//       conversation_id: activeId,
//       role: "user",
//       content,
//       created_at: new Date().toISOString(),
//     };
//
//     set({
//       messages: [...messages, userMsg],
//       streamingContent: "",
//       isStreaming: true,
//       error: null,
//       agentStatus: null,
//       _abortController: abortController,
//       _streamingConvId: streamingConvId,
//     });
//
//     await api.chatWithStream(
//       activeId,
//       content,
//       // onDelta — only apply if this conversation is still active
//       (delta) => {
//         const s = get();
//         if (s.activeId === streamingConvId) {
//           set({ streamingContent: s.streamingContent + delta });
//         }
//       },
//       // onDone — only update messages if still the active conversation
//       async () => {
//         const s = get();
//         if (s.activeId !== streamingConvId) return;
//         const conv = await api.getConversation(activeId);
//         const convs = await api.listConversations();
//         set({
//           messages: conv.messages || [],
//           streamingContent: "",
//           isStreaming: false,
//           conversations: convs,
//           agentStatus: null,
//           _abortController: null,
//           _streamingConvId: null,
//         });
//         api.getStudentProfile().then((p) => set({ profile: p }));
//       },
//       // onError — only report if still the active conversation
//       (err) => {
//         if (get().activeId === streamingConvId) {
//           set({ error: err, isStreaming: false, _abortController: null, _streamingConvId: null });
//         }
//       },
//       // onStatus — only show if still the active conversation
//       (status) => {
//         if (get().activeId === streamingConvId) {
//           set({ agentStatus: status });
//         }
//       },
//       abortController.signal
//     );
//   },
//
//   loadProfile: async () => {
//     try {
//       const p = await api.getStudentProfile();
//       set({ profile: p });
//     } catch {
//       // Profile fetch is optional
//     }
//   },
//
//   showProfile: async () => {
//     const { activeId } = get();
//     if (!activeId) return;
//
//     _abortActiveStream(get);
//
//     const abortController = new AbortController();
//     const streamingConvId = activeId;
//     const content = "我的档案";
//     const userMsg: Message = {
//       id: crypto.randomUUID(),
//       conversation_id: activeId,
//       role: "user",
//       content,
//       created_at: new Date().toISOString(),
//     };
//     set({
//       messages: [...get().messages, userMsg],
//       streamingContent: "",
//       isStreaming: true,
//       error: null,
//       agentStatus: null,
//       _abortController: abortController,
//       _streamingConvId: streamingConvId,
//     });
//     await api.chatWithStream(
//       activeId,
//       content,
//       (delta) => {
//         if (get().activeId === streamingConvId) {
//           set((s) => ({ streamingContent: s.streamingContent + delta }));
//         }
//       },
//       async () => {
//         if (get().activeId !== streamingConvId) return;
//         const conv = await api.getConversation(activeId);
//         set({
//           messages: conv.messages || [],
//           streamingContent: "",
//           isStreaming: false,
//           agentStatus: null,
//           _abortController: null,
//           _streamingConvId: null,
//         });
//         api.getStudentProfile().then((p) => set({ profile: p }));
//       },
//       (err) => {
//         if (get().activeId === streamingConvId) {
//           set({ error: err, isStreaming: false, _abortController: null, _streamingConvId: null });
//         }
//       },
//       (status) => {
//         if (get().activeId === streamingConvId) {
//           set({ agentStatus: status });
//         }
//       },
//       abortController.signal
//     );
//   },
// }));






import { create } from "zustand";
import type { Conversation, Message, StudentProfile, ProgressEvent } from "../types";
import * as api from "../api/chat";

// ✅ 在文件顶部添加这个兼容性 UUID 生成函数
const generateUUID = () => {
  // 优先使用原生 crypto.randomUUID
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // 降级方案：手动生成 UUID v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

interface ChatState {
  conversations: Conversation[];
  activeId: string | null;
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  error: string | null;
  profile: StudentProfile | null;
  agentStatus: string | null;
  progress: ProgressEvent | null;
  completed: boolean;
  totalResources: number;
  exerciseCount: number;
  _abortController: AbortController | null;
  _streamingConvId: string | null;

  loadConversations: () => Promise<void>;
  createConversation: () => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  setActive: (id: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  loadProfile: () => Promise<void>;
  showProfile: () => Promise<void>;
  clearProgress: () => void;
}

function _abortActiveStream(get: () => ChatState) {
  const { _abortController } = get();
  if (_abortController) {
    _abortController.abort();
  }
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeId: null,
  messages: [],
  streamingContent: "",
  isStreaming: false,
  error: null,
  profile: null,
  agentStatus: null,
  progress: null,
  completed: false,
  totalResources: 0,
  exerciseCount: 0,
  _abortController: null,
  _streamingConvId: null,

  loadConversations: async () => {
    const data = await api.listConversations();
    set({ conversations: data });
  },

  createConversation: async () => {
    _abortActiveStream(get);
    const conv = await api.createConversation();
    set({
      conversations: [conv, ...get().conversations],
      activeId: conv.id,
      messages: [],
      streamingContent: "",
      isStreaming: false,
      error: null,
      agentStatus: null,
      progress: null,
      completed: false,
      totalResources: 0,
      exerciseCount: 0,
      _abortController: null,
      _streamingConvId: null,
    });
  },

  deleteConversation: async (id) => {
    await api.deleteConversation(id);
    set((s) => {
      const filtered = s.conversations.filter((c) => c.id !== id);
      if (s.activeId === id) {
        _abortActiveStream(get);
        return {
          conversations: filtered,
          activeId: null,
          messages: [],
          streamingContent: "",
          isStreaming: false,
          agentStatus: null,
          progress: null,
          completed: false,
          totalResources: 0,
          _abortController: null,
          _streamingConvId: null,
        };
      }
      return { conversations: filtered };
    });
  },

  setActive: async (id) => {
    _abortActiveStream(get);
    const conv = await api.getConversation(id);
    set({
      activeId: id,
      messages: conv.messages || [],
      streamingContent: "",
      isStreaming: false,
      error: null,
      agentStatus: null,
      progress: null,
      completed: false,
      totalResources: 0,
      exerciseCount: 0,
      _abortController: null,
      _streamingConvId: null,
    });
  },

  sendMessage: async (content) => {
    const { activeId, messages } = get();
    if (!activeId || !content.trim()) return;

    // Abort any previous stream (shouldn't normally happen, but safe)
    _abortActiveStream(get);

    const abortController = new AbortController();
    const streamingConvId = activeId;

    // ✅ 修改第115行附近：将 crypto.randomUUID() 改为 generateUUID()
    const userMsg: Message = {
      id: generateUUID(),  // ← 这里修改
      conversation_id: activeId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };

    set({
      messages: [...messages, userMsg],
      streamingContent: "",
      isStreaming: true,
      error: null,
      agentStatus: null,
      progress: null,
      completed: false,
      totalResources: 0,
      _abortController: abortController,
      _streamingConvId: streamingConvId,
    });

    await api.chatWithStream(
      activeId,
      content,
      // onDelta
      (delta) => {
        const s = get();
        if (s.activeId === streamingConvId) {
          set({ streamingContent: s.streamingContent + delta });
        }
      },
      // onDone
      async () => {
        const s = get();
        if (s.activeId !== streamingConvId) return;
        const conv = await api.getConversation(activeId);
        const convs = await api.listConversations();
        set({
          messages: conv.messages || [],
          streamingContent: "",
          isStreaming: false,
          conversations: convs,
          agentStatus: null,
          progress: null,
          // Keep completed + totalResources so the "查看学习资料" button stays visible
          _abortController: null,
          _streamingConvId: null,
        });
        api.getStudentProfile().then((p) => set({ profile: p }));
      },
      // onError
      (err) => {
        if (get().activeId === streamingConvId) {
          set({ error: err, isStreaming: false, progress: null, completed: false, _abortController: null, _streamingConvId: null });
        }
      },
      // onStatus
      (status) => {
        if (get().activeId === streamingConvId) {
          set({ agentStatus: status });
        }
      },
      // onProgress
      (current, total, label, resourceType) => {
        if (get().activeId === streamingConvId) {
          set({ progress: { current, total, label, resource_type: resourceType } });
        }
      },
      // onComplete
      (total, quizTotal) => {
        if (get().activeId === streamingConvId) {
          set({ completed: true, totalResources: total, exerciseCount: quizTotal });
        }
      },
      abortController.signal
    );
  },

  clearProgress: () => set({ progress: null, completed: false, totalResources: 0, exerciseCount: 0 }),

  loadProfile: async () => {
    try {
      const p = await api.getStudentProfile();
      set({ profile: p });
    } catch {
      // Profile fetch is optional
    }
  },

  showProfile: async () => {
    const { activeId } = get();
    if (!activeId) return;

    _abortActiveStream(get);

    const abortController = new AbortController();
    const streamingConvId = activeId;
    const content = "我的档案";

    // ✅ 修改第180行附近：将 crypto.randomUUID() 改为 generateUUID()
    const userMsg: Message = {
      id: generateUUID(),  // ← 这里修改
      conversation_id: activeId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };

    set({
      messages: [...get().messages, userMsg],
      streamingContent: "",
      isStreaming: true,
      error: null,
      agentStatus: null,
      _abortController: abortController,
      _streamingConvId: streamingConvId,
    });
    await api.chatWithStream(
      activeId,
      content,
      (delta) => {
        if (get().activeId === streamingConvId) {
          set((s) => ({ streamingContent: s.streamingContent + delta }));
        }
      },
      async () => {
        if (get().activeId !== streamingConvId) return;
        const conv = await api.getConversation(activeId);
        set({
          messages: conv.messages || [],
          streamingContent: "",
          isStreaming: false,
          agentStatus: null,
          _abortController: null,
          _streamingConvId: null,
        });
        api.getStudentProfile().then((p) => set({ profile: p }));
      },
      (err) => {
        if (get().activeId === streamingConvId) {
          set({ error: err, isStreaming: false, _abortController: null, _streamingConvId: null });
        }
      },
      (status) => {
        if (get().activeId === streamingConvId) {
          set({ agentStatus: status });
        }
      },
      undefined, // onProgress — not needed for profile
      undefined, // onComplete — not needed for profile
      abortController.signal
    );
  },
}));