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

  // 60-second timeout on every request to allow complex AI agent reflection loops
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers, signal: controller.signal });
  } catch (err: any) {
    clearTimeout(timer);
    if (err?.name === 'AbortError') {
      throw new Error('Request timed out. Is the backend server running?');
    }
    throw new Error('Cannot connect to server. Please make sure the backend is running on port 8000.');
  }
  clearTimeout(timer);

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
  success?: boolean;
  token?: string;
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
  role?: 'user' | 'manager';
}

export interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
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
  try {
    await request('/api/auth/logout', { method: 'POST' });
  } catch {
    // Ignore logout errors — always clear local state
  }
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
  type: 'line' | 'bar' | 'pie' | 'table' | 'area' | 'stacked_bar' | 'horizontal_bar' |
        'combo' | 'histogram' | 'scatter' | 'bubble' | 'heatmap' | 'treemap' |
        'kpi_card' | 'gauge' | 'box_plot';
  chart_type?: string;
  x_axis?: string;
  y_axis?: string;
  stack_col?: string;
  value_col?: string;
  kpi_value?: number;
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

export interface MultiDBResult {
  database: string;
  connection_id: string;
  data: any[];
  columns: string[];
  sql: string | null;
  error: string | null;
  row_count: number;
  execution_ms: number;
}

export interface MultiDBPayload {
  results: MultiDBResult[];
  merged: boolean;
  merged_rows?: any[];
  merged_columns?: string[];
  summary: string;
}

/** List all chat sessions for the current user, optionally filtered by connectionId. */
export async function getChatSessions(connectionId?: string): Promise<ChatSessionMetaResponse[]> {
  const url = connectionId ? `/api/chat-sessions?connection_id=${connectionId}` : '/api/chat-sessions';
  return request<ChatSessionMetaResponse[]>(url);
}

export async function getChatSession(session_id: string): Promise<ChatSessionDetailsResponse> {
  return request<ChatSessionDetailsResponse>(`/api/chat-sessions/${session_id}`);
}

export async function renameChatSession(session_id: string, session_name: string): Promise<void> {
  await request(`/api/chat-sessions/${session_id}`, {
    method: 'PATCH',
    body: JSON.stringify({ session_name }),
  });
}

/**
 * Send a chat message.
 * connection_id is REQUIRED for database queries.
 */
export async function sendDbChatMessage(
  message: string,
  connection_id: string,
  session_id?: string | null,
  connection_ids?: string[],
): Promise<ChatMessageSendResponse> {
  return request<ChatMessageSendResponse>('/api/chat-message', {
    method: 'POST',
    body: JSON.stringify({
      message,
      connection_id,
      connection_ids: connection_ids && connection_ids.length > 1 ? connection_ids : undefined,
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
  status: 'pending' | 'approved' | 'rejected';
  is_admin_owned: boolean;
  created_by: string | null;
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

export async function updateConnection(id: string, data: {
  connection_name?: string;
  host?: string;
  port?: number;
  database_name?: string;
  username?: string;
  password?: string;
  ssl_enabled?: boolean;
}): Promise<DBConnectionItem> {
  return request<DBConnectionItem>(`/api/connections/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function getPendingConnections(): Promise<DBConnectionItem[]> {
  return request<DBConnectionItem[]>('/api/connections/pending');
}

export async function approveConnection(id: string): Promise<DBConnectionItem> {
  return request<DBConnectionItem>(`/api/connections/${id}/approve`, { method: 'POST' });
}

export async function rejectConnection(id: string): Promise<DBConnectionItem> {
  return request<DBConnectionItem>(`/api/connections/${id}/reject`, { method: 'POST' });
}

// ── Saved Queries ────────────────────────────────────────────────

export interface QueryExecutionItem {
  id: string;
  query_id: string;
  database_name: string;
  sql: string | null;
  status: string;
  result_json: any | null;
  error: string | null;
  execution_time_ms: number | null;
  row_count: number | null;
  created_at: string;
}

export interface SavedQueryItem {
  id: string;
  tenant_id: string;
  username: string;
  title: string;
  query_text: string;
  generated_sql?: string;
  created_at: string;
  executions: QueryExecutionItem[];
  
  // NEW Dynamic Execution Fields
  results: any[] | null;
  failed_sources?: { id: string; database_name?: string; error: string }[];
  execution_stats?: {
    time_ms: number;
    total_rows: number;
  };
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
  query_text?: string;
}

export async function updateSavedQuery(id: string, data: SavedQueryUpdateRequest): Promise<SavedQueryItem> {
  return request<SavedQueryItem>(`/api/queries/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export interface SavedQueryCreateRequest {
  connection_id: string;
  connection_ids?: string[];
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
  chart_type: string;
  chart_config: {
    x_axis: string;
    y_axis: string;
    stack_col?: string;
    value_col?: string;
    grouping?: string;
  };
  query_id: string;
  connection_id: string;
  user_id: string;
  tenant_id: string;
  created_at: string;
}

export interface ReportDataResponse {
  report_id: string;
  successful_data: any[];
  failed_sources: { id: string; database_name?: string; error: string }[];
  chart_type: string;
  chart_config: any;
  row_count: number;
  execution_time_ms: number;
  cache_status?: string;
  request_id?: string;
}

export async function getReports(): Promise<ReportItem[]> {
  return request<ReportItem[]>('/api/reports');
}

export async function createReport(data: {
  report_name: string;
  chart_type: string;
  chart_config: any;
  query_id: string;
  connection_id?: string;
}): Promise<ReportItem> {
  return request<ReportItem>('/api/reports', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteReport(id: string): Promise<void> {
  await request(`/api/reports/${id}`, { method: 'DELETE' });
}

export async function getReportData(id: string, limit: number = 1000, offset: number = 0): Promise<ReportDataResponse> {
  return request<ReportDataResponse>(`/api/reports/${id}/data?limit=${limit}&offset=${offset}`);
}

export interface SystemStatistics {
  queries_today: number;
  avg_execution_time: number;
  success_rate: number;
}

export async function getSystemStatistics(): Promise<SystemStatistics> {
  return request<SystemStatistics>('/api/reports/statistics');
}

// ── Admin Approvals ───────────────────────────────────────────────

export interface PendingUser {
  id: string;
  name: string | null;
  email: string;
  role: string;
  status: string;
  is_active: boolean;
  created_at: string;
}

export async function getPendingUsers(): Promise<PendingUser[]> {
  return request<PendingUser[]>('/api/admin/users/pending');
}

export async function approveUser(id: string): Promise<PendingUser> {
  return request<PendingUser>(`/api/admin/users/${id}/approve`, { method: 'POST' });
}

export async function rejectUser(id: string): Promise<PendingUser> {
  return request<PendingUser>(`/api/admin/users/${id}/reject`, { method: 'POST' });
}

export async function getAdminPendingConnections(): Promise<DBConnectionItem[]> {
  return request<DBConnectionItem[]>('/api/admin/connections/pending');
}

export async function adminApproveConnection(id: string): Promise<DBConnectionItem> {
  return request<DBConnectionItem>(`/api/admin/connections/${id}/approve`, { method: 'POST' });
}

export async function adminRejectConnection(id: string): Promise<DBConnectionItem> {
  return request<DBConnectionItem>(`/api/admin/connections/${id}/reject`, { method: 'POST' });
}

// ── Dashboard Builder ─────────────────────────────────────────────

export interface DashboardItem {
  id: string;
  user_id: string;
  tenant_id: string;
  connection_id: string | null;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface WidgetItem {
  id: string;
  dashboard_id: string;
  query_id: string | null;
  title: string;
  chart_type: string;
  config: { x_axis?: string; y_axis?: string; value_col?: string; [k: string]: any };
  grid_x: number;
  grid_y: number;
  grid_w: number;
  grid_h: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardDetail extends DashboardItem {
  widgets: WidgetItem[];
}

export interface WidgetCreateRequest {
  dashboard_id: string;
  query_id?: string;
  title: string;
  chart_type: string;
  config: { x_axis?: string; y_axis?: string; value_col?: string };
  grid_x: number;
  grid_y: number;
  grid_w: number;
  grid_h: number;
}

export interface LayoutItem {
  id: string;
  grid_x: number;
  grid_y: number;
  grid_w: number;
  grid_h: number;
}

export async function getDashboards(): Promise<DashboardItem[]> {
  return request<DashboardItem[]>('/api/dashboards');
}

export async function createDashboard(data: { name: string; connection_id?: string }): Promise<DashboardItem> {
  return request<DashboardItem>('/api/dashboards', { method: 'POST', body: JSON.stringify(data) });
}

export async function getDashboard(id: string): Promise<DashboardDetail> {
  return request<DashboardDetail>(`/api/dashboards/${id}`);
}

export async function updateDashboard(id: string, data: { name?: string; connection_id?: string }): Promise<DashboardItem> {
  return request<DashboardItem>(`/api/dashboards/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export async function deleteDashboard(id: string): Promise<void> {
  await request(`/api/dashboards/${id}`, { method: 'DELETE' });
}

export async function addWidget(data: WidgetCreateRequest): Promise<WidgetItem> {
  return request<WidgetItem>(`/api/dashboards/${data.dashboard_id}/widgets`, {
    method: 'POST', body: JSON.stringify(data),
  });
}

export async function updateWidget(dashboardId: string, widgetId: string, data: Partial<WidgetItem>): Promise<WidgetItem> {
  return request<WidgetItem>(`/api/dashboards/${dashboardId}/widgets/${widgetId}`, {
    method: 'PUT', body: JSON.stringify(data),
  });
}

export async function deleteWidget(dashboardId: string, widgetId: string): Promise<void> {
  await request(`/api/dashboards/${dashboardId}/widgets/${widgetId}`, { method: 'DELETE' });
}

export async function saveLayout(dashboardId: string, layout: LayoutItem[]): Promise<void> {
  await request(`/api/dashboards/${dashboardId}/layout`, {
    method: 'POST', body: JSON.stringify({ layout }),
  });
}

export async function getWidgetData(dashboardId: string, widgetId: string, limit: number = 1000, offset: number = 0): Promise<ReportDataResponse> {
  return request<ReportDataResponse>(`/api/dashboards/${dashboardId}/widgets/${widgetId}/data?limit=${limit}&offset=${offset}`);
}
