// Centralised API client — all backend calls in one place.

const BASE_URL = 'http://localhost:8000';

let authToken: string | null = null;

export function setToken(token: string | null) {
  authToken = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    if (res.status === 401) {
      window.dispatchEvent(new Event('auth_error'));
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    let message = 'Request failed';
    if (typeof err.detail === 'string') {
      message = err.detail;
    } else if (Array.isArray(err.detail)) {
      message = err.detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join('; ');
    } else if (err.detail) {
      message = JSON.stringify(err.detail);
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  session_id: string;
  role: string;
  expires_in: number;
}

export interface RegisterRequest {
  name?: string;
  email: string;
  phone_number?: string;
  password: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export async function register(data: RegisterRequest): Promise<{ id: string; email: string }> {
  return request<{ id: string; email: string }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Login — accepts a real email OR a shorthand username (admin / user).
 * The backend resolves usernames to their seeded email.
 */
export async function login(emailOrUsername: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email: emailOrUsername, password }),
  });
}

export async function logout(): Promise<void> {
  await request('/api/auth/logout', { method: 'POST' });
}

export async function getMe(): Promise<UserProfile> {
  return request<UserProfile>('/api/auth/me');
}

// ── Services ──────────────────────────────────────────────────────

export interface DatabaseConnectionRequest {
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
}

export interface ConnectionResponse {
  status: string;
  service: string;
  details: Record<string, unknown>;
}

export async function connectDatabase(payload: DatabaseConnectionRequest): Promise<ConnectionResponse> {
  return request<ConnectionResponse>('/api/services/connect/database', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ── Chat ──────────────────────────────────────────────────────────

export interface ChartConfig {
  type: 'line' | 'bar' | 'pie' | 'table';
  chart_type?: 'line' | 'bar' | 'pie';
  x_axis?: string;
  y_axis?: string;
  data: any[];
}

export interface ChatResponse {
  summary: string;
  sql?: string;
  preview_rows?: any[];
  metadata?: {
    row_count: number;
    execution_time: number;
  };
  chart?: ChartConfig;
  // Legacy fields
  response: string;
  tool_used?: string;
}

export interface HistoryMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export async function sendMessage(message: string, session_id: string): Promise<ChatResponse> {
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id }),
  });
}

export async function getChatHistory(session_id: string): Promise<{ messages: HistoryMessage[] }> {
  return request<{ messages: HistoryMessage[] }>(`/api/chat/history?session_id=${session_id}`);
}

// ── Persistent Chat Sessions ──────────────────────────────────────

export interface ChatSessionMetaResponse {
  session_id: string;
  connection_id: string | null;
  session_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageItemResponse {
  id: string;
  role: 'user' | 'agent';
  message_text: string;
  generated_sql: string | null;
  query_result_snapshot: any | null;
  created_at: string;
}

export interface ChatSessionDetailsResponse {
  session_id: string;
  connection_id: string | null;
  session_name: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessageItemResponse[];
}

export interface ChatMessageSendResponse {
  user_message: ChatMessageItemResponse;
  agent_message: ChatMessageItemResponse;
  tool_used: string | null;
  metadata: { plan?: any; session_id?: string; [key: string]: any };
}

/** List all chat sessions for the current user (global — not connection-scoped). */
export async function getChatSessions(): Promise<ChatSessionMetaResponse[]> {
  return request<ChatSessionMetaResponse[]>('/api/chat-sessions');
}

export async function getChatSession(session_id: string): Promise<ChatSessionDetailsResponse> {
  return request<ChatSessionDetailsResponse>(`/api/chat-sessions/${session_id}`);
}

/**
 * Send a chat message.
 * connection_id is optional — omit to chat without a database connection.
 */
export async function sendDbChatMessage(
  message: string,
  session_id?: string | null,
): Promise<ChatMessageSendResponse> {
  return request<ChatMessageSendResponse>('/api/chat-message', {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: session_id ?? undefined,
    }),
  });
}

// ── Connections ───────────────────────────────────────────────────

export interface DBConnectionItem {
  id: string;
  connection_name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  ssl_enabled: boolean;
  created_at: string;
}

export async function getConnections(): Promise<DBConnectionItem[]> {
  return request<DBConnectionItem[]>('/api/connections');
}

export async function createConnection(data: {
  connection_name: string;
  db_type: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  ssl_enabled?: boolean;
}): Promise<DBConnectionItem> {
  return request<DBConnectionItem>('/api/connections', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteConnection(id: string): Promise<void> {
  await request(`/api/connections/${id}`, { method: 'DELETE' });
}

// ── Saved Queries ────────────────────────────────────────────────

export interface SavedQueryItem {
  id: string;
  connection_id: string;
  query_name: string;
  natural_language_query: string;
  generated_sql: string;
  query_result_snapshot: unknown[] | null;
  execution_time_ms: number | null;
  row_count: number | null;
  created_at: string;
}

export async function getSavedQueries(): Promise<SavedQueryItem[]> {
  return request<SavedQueryItem[]>('/api/queries');
}

export async function deleteSavedQuery(id: string): Promise<void> {
  await request(`/api/queries/${id}`, { method: 'DELETE' });
}

export interface SavedQueryCreateRequest {
  connection_id: string;
  query_name: string;
  natural_language_query: string;
  generated_sql: string;
  query_result_snapshot?: any;
  execution_time_ms?: number;
  row_count?: number;
}

export async function createSavedQuery(data: SavedQueryCreateRequest): Promise<SavedQueryItem> {
  return request<SavedQueryItem>('/api/queries', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
