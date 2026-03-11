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
    if (res.status === 401 || res.status === 404) {
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
  expires_in: number;
}

export interface RegisterRequest {
  name?: string;
  email: string;
  phone_number?: string;
  password: string;
}

export async function register(data: RegisterRequest): Promise<{ id: string; email: string }> {
  return request<{ id: string; email: string }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(): Promise<void> {
  await request('/api/auth/logout', { method: 'POST' });
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

export interface ChatResponse {
  response: string;
  tool_used?: string;
  metadata?: Record<string, unknown>;
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
