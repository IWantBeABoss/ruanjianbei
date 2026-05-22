export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface User {
  id: string;
  username: string;
  created_at: string;
}

export interface Exercise {
  id: string;
  conversation_id: string;
  subject: string;
  question_type: "choice" | "fill_blank" | "true_false";
  question_number: number;
  question: string;
  options: string[];
  answer: string;
  explanation: string;
  created_at: string;
}

export interface StudentProfile {
  id: string;
  major_background: string;
  knowledge_base: string;
  cognitive_style: string;
  learning_goals: string;
  weak_points: string;
  schedule_preference: string;
  content_preference: string;
  updated_at: string | null;
}

export interface Resource {
  id: string;
  conversation_id: string;
  resource_type: string;
  topic: string;
  content: string;
  file_name: string;
  reviewed: boolean;
  created_at: string;
}

export interface ProgressEvent {
  current: number;
  total: number;
  label: string;
  resource_type: string;
}
