import { create } from "zustand";
import * as api from "../api/chat";

interface AuthState {
  token: string | null;
  user: { id: string; username: string } | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("token"),
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (username, password) => {
    const data = await api.login(username, password);
    localStorage.setItem("token", data.access_token);
    set({ token: data.access_token, user: data.user, isAuthenticated: true });
  },

  register: async (username, password) => {
    const data = await api.register(username, password);
    localStorage.setItem("token", data.access_token);
    set({ token: data.access_token, user: data.user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      set({ isLoading: false });
      return;
    }
    try {
      const user = await api.getMe();
      set({ token, user, isAuthenticated: true, isLoading: false });
    } catch {
      localStorage.removeItem("token");
      set({ token: null, isLoading: false });
    }
  },
}));
