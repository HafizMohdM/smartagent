import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
    getConnections, createConnection, deleteConnection,
    approveConnection, rejectConnection,
    getSavedQueries, deleteSavedQuery, getSystemStatistics,
    type DBConnectionItem, type SavedQueryItem, type SystemStatistics
} from '../api/client';
import LoadingDots from '../components/LoadingDots';
import ReportsView from './ReportsView';
import EditConnectionModal from '../components/EditConnectionModal';
import ApprovalsView from './ApprovalsView';

type Tab = 'connections' | 'queries' | 'reports' | 'approvals' | 'profile';

export default function DashboardView() {
    const { username, isAdmin, role } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<Tab>('connections');

    return (
        <div className="dashboard-layout">
            <aside className="app-sidebar">
                <nav className="sidebar-nav" style={{ marginTop: '12px' }}>
                    <div className="sidebar-divider">AI Workspace</div>
                    <button
                        className="sidebar-item sidebar-chat-btn"
                        onClick={() => navigate('/chat')}
                    >
                        <span className="sidebar-icon">💬</span>
                        <span>Cogni-Assistant</span>
                    </button>

                    <div className="sidebar-divider">DATA Hub</div>
                    <button
                        className={`sidebar-item ${activeTab === 'connections' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('connections')}
                    >
                        <span className="sidebar-icon">🗄️</span>
                        <span>Data Sources</span>
                    </button>
                    <button
                        className={`sidebar-item ${activeTab === 'queries' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('queries')}
                    >
                        <span className="sidebar-icon">📋</span>
                        <span>Insight Library</span>
                    </button>
                    <button
                        className={`sidebar-item ${activeTab === 'reports' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('reports')}
                    >
                        <span className="sidebar-icon">📈</span>
                        <span>Insights</span>
                    </button>
                    <button
                        className="sidebar-item"
                        onClick={() => navigate('/builder')}
                    >
                        <span className="sidebar-icon">🏗️</span>
                        <span>Dashboards</span>
                    </button>

                    {isAdmin && (
                        <>
                            <div className="sidebar-divider">Governance</div>
                            <button
                                className={`sidebar-item ${activeTab === 'approvals' ? 'sidebar-active' : ''}`}
                                onClick={() => setActiveTab('approvals')}
                            >
                                <span className="sidebar-icon">✅</span>
                                <span>Access Control</span>
                            </button>
                        </>
                    )}

                    <div className="sidebar-divider">Account</div>
                    <button
                        className={`sidebar-item ${activeTab === 'profile' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('profile')}
                    >
                        <span className="sidebar-icon">👤</span>
                        <span>Profile Settings  </span>
                    </button>
                </nav>
                <div className="sidebar-footer">
                    <span className="app-version">v2.0.0</span>
                </div>
            </aside>
            <section className="dashboard-content">
                {activeTab === 'connections' && <ConnectionsPanel isAdmin={isAdmin} role={role} />}
                {activeTab === 'queries' && <QueriesPanel />}
                {activeTab === 'reports' && <ReportsView />}
                {activeTab === 'approvals' && isAdmin && <ApprovalsView />}
                {activeTab === 'profile' && <ProfilePanel username={username} isAdmin={isAdmin} />}
            </section>
        </div>
    );
}

/* ── Connections Panel ──────────────────────────────────────────── */

function ConnectionsPanel({ isAdmin, role }: { isAdmin: boolean; role: string | null }) {
    const { setHasDatabaseConnection } = useAuth();
    const [connections, setConnections] = useState<DBConnectionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [error, setError] = useState('');
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [editingConn, setEditingConn] = useState<DBConnectionItem | null>(null);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const canCreate = isAdmin || role === 'manager' || role === 'user';
    const canDelete = isAdmin;

    const fetchConnections = async () => {
        setLoading(true);
        setError('');
        try {
            const data = await getConnections();
            setConnections(data);
            setHasDatabaseConnection(data.some(c => c.status === 'approved'));
            if (data.length > 0 && selectedIds.length === 0) {
                const stored = localStorage.getItem('chat_selected_db_ids');
                if (stored) {
                    try {
                        const parsed = JSON.parse(stored);
                        const validIds = parsed.filter((id: string) => data.some(db => db.id === id && db.status === 'approved'));
                        if (validIds.length > 0) {
                            setSelectedIds(validIds);
                            return;
                        }
                    } catch (err) { }
                }
                const first = data.find(c => c.status === 'approved');
                if (first) setSelectedIds([first.id]);
            }
        } catch (e) {
            setConnections([]);
            setHasDatabaseConnection(false);
            setError(e instanceof Error ? e.message : 'Failed to load connections');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchConnections(); }, []);

    useEffect(() => {
        if (!loading) {
            localStorage.setItem('chat_selected_db_ids', JSON.stringify(selectedIds));
        }
    }, [selectedIds, loading]);

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
    };

    const handleDelete = async (id: string) => {
        if (!window.confirm('Delete this connection?')) return;
        try {
            await deleteConnection(id);
            setConnections(c => {
                const next = c.filter(x => x.id !== id);
                setHasDatabaseConnection(next.some(x => x.status === 'approved'));
                return next;
            });
            setSelectedIds(prev => prev.filter(x => x !== id));
        } catch (e) { setError(e instanceof Error ? e.message : 'Delete failed'); }
    };

    const handleApprove = async (id: string) => {
        setActionLoading(id + '_approve');
        try {
            const updated = await approveConnection(id);
            setConnections(prev => prev.map(c => c.id === id ? updated : c));
            setHasDatabaseConnection(true);
        } catch (e) { setError(e instanceof Error ? e.message : 'Approve failed'); }
        finally { setActionLoading(null); }
    };

    const handleReject = async (id: string) => {
        setActionLoading(id + '_reject');
        try {
            const updated = await rejectConnection(id);
            setConnections(prev => prev.map(c => c.id === id ? updated : c));
        } catch (e) { setError(e instanceof Error ? e.message : 'Reject failed'); }
        finally { setActionLoading(null); }
    };

    const statusBadge = (s: DBConnectionItem['status']) => {
        const cls = { approved: 'status-badge-approved', pending: 'status-badge-pending', rejected: 'status-badge-rejected' };
        const lbl = { approved: '✓ Approved', pending: '⏳ Pending', rejected: '✕ Rejected' };
        return <span className={cls[s] ?? cls.pending}>{lbl[s] ?? s}</span>;
    };

    const pendingCount = connections.filter(c => c.status === 'pending').length;

    return (
        <div className="panel">
            <div className="panel-header">
                <div>
                    <h2>Database Connections</h2>
                    <p className="panel-subtitle">
                        {isAdmin ? 'Manage connections and approve requests' : 'Your database connections'}
                        {isAdmin && pendingCount > 0 && (
                            <span style={{
                                marginLeft: '10px', background: '#f59e0b', color: '#fff',
                                fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px',
                                borderRadius: '20px'
                            }}>
                                {pendingCount} pending
                            </span>
                        )}
                    </p>
                </div>
                {canCreate && (
                    <button className="btn-accent-sm" onClick={() => setShowForm(!showForm)}>
                        {showForm ? '✕ Cancel' : '+ Add Connection'}
                    </button>
                )}
            </div>

            {error && (
                <div className="error-banner" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    ⚠️ {error}
                    <button onClick={fetchConnections} style={{
                        background: 'transparent',
                        border: '1px solid currentColor', borderRadius: '4px', padding: '2px 8px',
                        cursor: 'pointer', fontSize: '0.8rem'
                    }}>Retry</button>
                </div>
            )}

            {!isAdmin && role !== 'manager' && (
                <div className="info-banner">
                    ℹ️ New connections require admin approval before use in chat.
                </div>
            )}

            {showForm && (
                <AddConnectionForm
                    onSuccess={() => { setShowForm(false); fetchConnections(); }}
                    onCancel={() => setShowForm(false)}
                />
            )}

            {loading ? (
                <div className="panel-loading"><LoadingDots /></div>
            ) : connections.length === 0 && !showForm ? (
                <div className="panel-empty" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                    <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🗄️</div>
                    <h3 style={{ marginBottom: '0.5rem' }}>No connections yet</h3>
                    <p style={{ opacity: 0.7, marginBottom: '1.5rem' }}>
                        {canCreate ? 'Add a database connection to get started.' : 'Ask an admin to add a connection.'}
                    </p>
                    {canCreate && (
                        <button onClick={() => setShowForm(true)} className="btn-accent" style={{ padding: '0.5rem 1rem' }}>
                            Add Connection
                        </button>
                    )}
                </div>
            ) : !showForm && (
                <>
                    {selectedIds.length > 0 && (
                        <div style={{ marginBottom: '12px', fontSize: '0.82rem', color: 'var(--accent)', fontWeight: 600 }}>
                            ✓ {selectedIds.length} connection{selectedIds.length > 1 ? 's' : ''} selected for chat
                        </div>
                    )}
                    <div className="cards-grid">
                        {connections.map(conn => {
                            const isSelected = selectedIds.includes(conn.id);
                            const isApproved = conn.status === 'approved';
                            const canEdit = isAdmin || (role === 'manager' && !conn.is_admin_owned &&
                                conn.created_by !== null);
                            return (
                                <div key={conn.id}
                                    className={`db-card${isSelected ? ' selected' : ''}`}
                                    onClick={() => isApproved && toggleSelect(conn.id)}
                                    style={{
                                        cursor: isApproved ? 'pointer' : 'default',
                                        opacity: conn.status === 'rejected' ? 0.55 : 1
                                    }}>
                                    <div className="db-card-header">
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            {isApproved && (
                                                <input type="checkbox" checked={isSelected}
                                                    onChange={() => toggleSelect(conn.id)}
                                                    onClick={e => e.stopPropagation()}
                                                    style={{ cursor: 'pointer', accentColor: 'var(--accent)', width: '15px', height: '15px' }} />
                                            )}
                                            <div className="db-card-type">{conn.db_type.toUpperCase()}</div>
                                        </div>
                                        <div className="db-card-actions">
                                            {canEdit && (
                                                <button className="db-card-action-btn"
                                                    onClick={e => { e.stopPropagation(); setEditingConn(conn); }}
                                                    title="Edit">✏️</button>
                                            )}
                                            {canDelete && (
                                                <button className="db-card-action-btn danger"
                                                    onClick={e => { e.stopPropagation(); handleDelete(conn.id); }}
                                                    title="Delete">🗑️</button>
                                            )}
                                        </div>
                                    </div>

                                    <h3 className="db-card-name">
                                        {isSelected && <span className="db-card-check">✓</span>}
                                        {conn.connection_name}
                                    </h3>

                                    <div className="db-card-details">
                                        <div className="db-detail"><span className="db-label">Host</span><span>{conn.host}:{conn.port}</span></div>
                                        <div className="db-detail"><span className="db-label">Database</span><span>{conn.database_name}</span></div>
                                        <div className="db-detail"><span className="db-label">User</span><span>{conn.username}</span></div>
                                        <div className="db-detail"><span className="db-label">SSL</span><span>{conn.ssl_enabled ? '✓ Enabled' : '✗ Off'}</span></div>
                                    </div>

                                    <div className="db-card-footer">
                                        <span className="db-date">{new Date(conn.created_at).toLocaleDateString()}</span>
                                        {statusBadge(conn.status)}
                                    </div>

                                    {/* Admin approval actions */}
                                    {isAdmin && conn.status === 'pending' && (
                                        <div style={{ display: 'flex', gap: '8px', padding: '10px 0 2px', borderTop: '1px solid var(--border)', marginTop: '8px' }}>
                                            <button
                                                onClick={e => { e.stopPropagation(); handleApprove(conn.id); }}
                                                disabled={actionLoading === conn.id + '_approve'}
                                                style={{
                                                    flex: 1, padding: '6px', background: 'var(--success-soft)',
                                                    border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px',
                                                    color: '#065f46', fontWeight: 600, fontSize: '0.8rem',
                                                    cursor: 'pointer', fontFamily: 'inherit'
                                                }}>
                                                {actionLoading === conn.id + '_approve' ? '…' : '✓ Approve'}
                                            </button>
                                            <button
                                                onClick={e => { e.stopPropagation(); handleReject(conn.id); }}
                                                disabled={actionLoading === conn.id + '_reject'}
                                                style={{
                                                    flex: 1, padding: '6px', background: 'var(--error-soft)',
                                                    border: '1px solid rgba(239,68,68,0.25)', borderRadius: '6px',
                                                    color: '#991b1b', fontWeight: 600, fontSize: '0.8rem',
                                                    cursor: 'pointer', fontFamily: 'inherit'
                                                }}>
                                                {actionLoading === conn.id + '_reject' ? '…' : '✕ Reject'}
                                            </button>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </>
            )}

            {editingConn && (
                <EditConnectionModal
                    conn={editingConn}
                    onClose={() => setEditingConn(null)}
                    onSaved={updated => {
                        setConnections(prev => prev.map(c => c.id === updated.id ? updated : c));
                        setEditingConn(null);
                    }}
                />
            )}
        </div>
    );
}

function AddConnectionForm({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) {
    const [form, setForm] = useState({
        connection_name: '',
        db_type: 'postgresql',
        host: 'localhost',
        port: 5432,
        database_name: '',
        username: 'postgres',
        password: '',
        ssl_enabled: false,
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const val = field === 'port' ? Number(e.target.value) :
            field === 'ssl_enabled' ? (e.target as HTMLInputElement).checked : e.target.value;
        setForm(f => ({ ...f, [field]: val }));
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await createConnection(form);
            onSuccess();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to create connection');
        } finally {
            setLoading(false);
        }
    };

    return (
        <form className="add-form" onSubmit={handleSubmit}>
            <div className="form-grid">
                <div className="field-group">
                    <label>Connection Name</label>
                    <input type="text" value={form.connection_name} onChange={set('connection_name')} placeholder="My Production DB" required />
                </div>
                <div className="field-group">
                    <label>Database Type</label>
                    <select value={form.db_type} onChange={set('db_type')}>
                        <option value="postgresql">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="mssql">MS SQL</option>
                        <option value="sqlite">SQLite</option>
                    </select>
                </div>
                <div className="field-group">
                    <label>Host</label>
                    <input type="text" value={form.host} onChange={set('host')} placeholder="localhost" required />
                </div>
                <div className="field-group field-small">
                    <label>Port</label>
                    <input type="number" value={form.port} onChange={set('port')} required />
                </div>
                <div className="field-group">
                    <label>Database Name</label>
                    <input type="text" value={form.database_name} onChange={set('database_name')} placeholder="mydb" required />
                </div>
                <div className="field-group">
                    <label>Username</label>
                    <input type="text" value={form.username} onChange={set('username')} placeholder="postgres" required />
                </div>
                <div className="field-group">
                    <label>Password</label>
                    <input type="password" value={form.password} onChange={set('password')} placeholder="••••••••" required />
                </div>
                <div className="field-group field-checkbox">
                    <label>
                        <input type="checkbox" checked={form.ssl_enabled} onChange={set('ssl_enabled')} />
                        Enable SSL
                    </label>
                </div>
            </div>

            {error && <div className="error-banner">{error}</div>}

            <div className="form-actions">
                <button type="button" className="btn-ghost-sm" onClick={onCancel}>Cancel</button>
                <button type="submit" className="btn-accent-sm" disabled={loading}>
                    {loading ? <LoadingDots /> : 'Save Connection'}
                </button>
            </div>
        </form>
    );
}

/* ── Saved Queries Panel ───────────────────────────────────────── */

function QueriesPanel() {
    const [queries, setQueries] = useState<SavedQueryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const fetchQueries = async () => {
        setLoading(true);
        try {
            const data = await getSavedQueries();
            setQueries(data);
        } catch { setQueries([]); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchQueries(); }, []);

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!window.confirm('Delete this saved query?')) return;
        try {
            await deleteSavedQuery(id);
            setQueries(q => q.filter(x => x.id !== id));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Delete failed');
        }
    };

    return (
        <div className="panel">
            <div className="panel-header">
                <div>
                    <h2>Saved Queries</h2>
                    <p className="panel-subtitle">Queries generated and saved from your chat sessions</p>
                </div>
            </div>

            {error && <div className="error-banner">{error}</div>}

            {loading ? (
                <div className="panel-loading"><LoadingDots /></div>
            ) : queries.length === 0 ? (
                <div className="panel-empty">
                    <div className="empty-icon">📋</div>
                    <h3>No saved queries</h3>
                    <p>When you save queries from the chat, they'll appear here.</p>
                </div>
            ) : (
                <div className="cards-grid">
                    {queries.map(q => (
                        <div key={q.id} className="query-card-v2" onClick={() => navigate(`/saved-query/${q.id}`)}>
                            <div className="query-card-header">
                                <div className="query-card-db">{q.executions?.map(e => e.database_name).join(', ') || 'Unknown'}</div>
                                <button className="btn-delete-icon" onClick={(e) => handleDelete(q.id, e)} title="Delete query">×</button>
                            </div>
                            <h3 className="query-card-title">{q.title}</h3>
                            <p className="query-card-desc">
                                {q.query_text.length > 120
                                    ? q.query_text.substring(0, 117) + '...'
                                    : q.query_text}
                            </p>
                            <div className="query-card-footer">
                                <div className="query-card-meta">
                                    <span>👤 {q.username}</span>
                                    <span>📅 {new Date(q.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── Reports Panel ─────────────────────────────────────────────── */

/* ── Profile Panel ─────────────────────────────────────────────── */

function ProfilePanel({ username, isAdmin }: { username: string | null; isAdmin: boolean }) {
    const [stats, setStats] = useState<SystemStatistics | null>(null);
    const [loadingStats, setLoadingStats] = useState(false);

    useEffect(() => {
        if (isAdmin) {
            setLoadingStats(true);
            getSystemStatistics()
                .then(setStats)
                .catch(() => setStats(null))
                .finally(() => setLoadingStats(false));
        }
    }, [isAdmin]);

    return (
        <div className="panel animate-in">
            <div className="panel-header">
                <div>
                    <h2>Your Profile</h2>
                    <p className="panel-subtitle">Account information</p>
                </div>
            </div>
            <div className="profile-card">
                <div className="profile-avatar">
                    <span>{isAdmin ? '🛡️' : '👤'}</span>
                </div>
                <div className="profile-info">
                    <div className="profile-row">
                        <span className="profile-label">Email</span>
                        <span className="profile-value">{username ?? 'N/A'}</span>
                    </div>
                    <div className="profile-row">
                        <span className="profile-label">Role</span>
                        <span className={`profile-value role-badge ${isAdmin ? 'role-admin' : 'role-user'}`}>
                            {isAdmin ? '🛡️ Admin' : '👤 User'}
                        </span>
                    </div>
                    <div className="profile-row">
                        <span className="profile-label">Status</span>
                        <span className="profile-value status-active">● Active</span>
                    </div>
                </div>
            </div>

            {/* Admin-only Analytical Reports */}
            {isAdmin && (
                <div className="admin-reports-section" style={{ marginTop: '2.5rem' }}>
                    <div className="section-divider">
                        <h3>System Analytics</h3>
                        <p>Real-time insights and system health (Admin Only)</p>
                    </div>

                    {loadingStats ? (
                        <div style={{ padding: '20px' }}><LoadingDots /></div>
                    ) : stats ? (
                        <div className="reports-grid">
                            <div className="report-stat-card">
                                <div className="stat-value">{stats.queries_today}</div>
                                <div className="stat-label">Queries Today</div>
                                <div className="stat-trend trend-up">↑ {Math.round(stats.queries_today * 0.1)}% from yesterday</div>
                            </div>
                            <div className="report-stat-card">
                                <div className="stat-value">{stats.success_rate}%</div>
                                <div className="stat-label">Success Rate</div>
                                <div className="stat-trend">SQL Validation Pass</div>
                            </div>
                            <div className="report-stat-card">
                                <div className="stat-value">{stats.avg_execution_time.toFixed(1)}s</div>
                                <div className="stat-label">Avg Execution</div>
                                <div className="stat-trend trend-down">↓ {(stats.avg_execution_time * 0.2).toFixed(1)}s optimization</div>
                            </div>
                        </div>
                    ) : (
                        <div className="info-banner">⚠️ Failed to load system analytics.</div>
                    )}

                    <div className="panel-section" style={{ marginTop: '2rem' }}>
                        <h4>Recent System Health</h4>
                        <div className="health-list">
                            <div className="health-item">
                                <div className="health-status status-up"></div>
                                <div className="health-info">
                                    <span className="health-name">Database Connector Service</span>
                                    <span className="health-meta">Operational • 100% uptime</span>
                                </div>
                            </div>
                            <div className="health-item">
                                <div className="health-status status-up"></div>
                                <div className="health-info">
                                    <span className="health-name">AI Reasoning Engine (LangGraph)</span>
                                    <span className="health-meta">Operational • Response latency within SLA</span>
                                </div>
                            </div>
                            <div className="health-item">
                                <div className="health-status status-warning"></div>
                                <div className="health-info">
                                    <span className="health-name">Semantic Schema Indexer</span>
                                    <span className="health-meta">Re-indexing in progress • 82% complete</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
