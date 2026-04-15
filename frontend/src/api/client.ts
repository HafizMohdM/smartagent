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

/** List all chat sessions for the current user, optionally filtered by connectionId. */
export async function getChatSessions(connectionId?: string): Promise<ChatSessionMetaResponse[]> {
  const url = connectionId ? `/api/chat-sessions?connection_id=${connectionId}` : '/api/chat-sessions';
  return request<ChatSessionMetaResponse[]>(url);
}

export async function getChatSession(session_id: string): Promise<ChatSessionDetailsResponse> {
  return request<ChatSessionDetailsResponse>(`/api/chat-sessions/${session_id}`);
}

/**
 * Send a chat message.
 * connection_id is REQUIRED for database queries.
 */
export async function sendDbChatMessage(
  message: string,
  connection_id: string,
  session_id?: string | null,
): Promise<ChatMessageSendResponse> {
  return request<ChatMessageSendResponse>('/api/chat-message', {
    method: 'POST',
    body: JSON.stringify({
      message,
      connection_id,
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
  tenant_id: string;
  database_name: string;
  username: string;
  title: string;
  natural_language_query: string;
  query: string;
  query_result_snapshot: any | null;
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

export async function getSavedQueryPreview(id: string): Promise<SavedQueryItem> {
  return request<SavedQueryItem>(`/api/queries/${id}/preview`);
}

export async function getSavedQuery(id: string): Promise<SavedQueryItem> {
  // Alias or direct fetch if we don't want to execute. 
  // However, since the requirements say "execute on load", we keep using preview for now 
  // or add a simple getter. Let's add a proper preview/execution one.
  return request<SavedQueryItem>(`/api/queries/${id}/preview`);
}

export interface SavedQueryUpdateRequest {
  title?: string;
  query?: string;
}

export async function updateSavedQuery(id: string, data: SavedQueryUpdateRequest): Promise<SavedQueryItem> {
  return request<SavedQueryItem>(`/api/queries/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export interface SavedQueryCreateRequest {
  connection_id: string;
  title: string;
  natural_language_query: string;
  query: string;
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
// ── Reports ───────────────────────────────────────────────────────

export interface ReportItem {
  id: string;
  report_name: string;
  chart_type: 'bar' | 'line' | 'pie' | 'table';
  chart_config: {
    x_axis: string;
    y_axis: string;
    grouping?: string;
  };
  saved_query_id: string;
  connection_id: string;
  user_id: string;
  tenant_id: string;
  created_at: string;
}

export interface ReportDataResponse {
  report_id: string;
  data: any[];
  chart_type: string;
  chart_config: any;
  row_count: number;
  execution_time_ms: number;
}

export async function getReports(): Promise<ReportItem[]> {
  return request<ReportItem[]>('/api/reports');
}

export async function createReport(data: {
  report_name: string;
  chart_type: string;
  chart_config: any;
  saved_query_id: string;
  connection_id: string;
}): Promise<ReportItem> {
  return request<ReportItem>('/api/reports', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteReport(id: string): Promise<void> {
  await request(`/api/reports/${id}`, { method: 'DELETE' });
}

export async function getReportData(id: string): Promise<ReportDataResponse> {
  return request<ReportDataResponse>(`/api/reports/${id}/data`);
}

export interface SystemStatistics {
  queries_today: number;
  avg_execution_time: number;
  success_rate: number;
}

export async function getSystemStatistics(): Promise<SystemStatistics> {
  return request<SystemStatistics>('/api/reports/statistics');
}
