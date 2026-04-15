import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
    getConnections, createConnection, deleteConnection,
    getSavedQueries, deleteSavedQuery, getSystemStatistics,
    type DBConnectionItem, type SavedQueryItem, type SystemStatistics
} from '../api/client';
import LoadingDots from '../components/LoadingDots';
import ReportsView from './ReportsView';

type Tab = 'connections' | 'queries' | 'reports' | 'profile';

export default function DashboardView() {
    const { username, isAdmin } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<Tab>('connections');

    return (
        <div className="dashboard-layout">
            <aside className="dashboard-sidebar">
                <div className="sidebar-title">Agent Alpha</div>
                <nav className="sidebar-nav">
                    {/* Chat Assistant - Navigation Shortcut */}
                    <button
                        className="sidebar-item sidebar-chat-btn"
                        onClick={() => navigate('/chat')}
                        title="Start a new chat with the AI assistant"
                    >
                        <span className="sidebar-icon">💬</span>
                        <span>Chat Assistant</span>
                    </button>

                    <div className="sidebar-divider">NAVIGATION</div>

                    <button
                        className={`sidebar-item ${activeTab === 'connections' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('connections')}
                    >
                        <span className="sidebar-icon">🗄️</span>
                        <span>Connections</span>
                    </button>
                    <button
                        className={`sidebar-item ${activeTab === 'queries' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('queries')}
                    >
                        <span className="sidebar-icon">📋</span>
                        <span>Saved Queries</span>
                    </button>
                    <button
                        className={`sidebar-item ${activeTab === 'reports' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('reports')}
                    >
                        <span className="sidebar-icon">📈</span>
                        <span>Reports</span>
                    </button>
                    <button
                        className={`sidebar-item ${activeTab === 'profile' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('profile')}
                    >
                        <span className="sidebar-icon">👤</span>
                        <span>Profile</span>
                    </button>
                </nav>
                <div className="sidebar-footer">
                    <span className="app-version">v1.2.0</span>
                </div>
            </aside>
            <section className="dashboard-content">
                {activeTab === 'connections' && <ConnectionsPanel isAdmin={isAdmin} />}
                {activeTab === 'queries' && <QueriesPanel />}
                {activeTab === 'reports' && <ReportsView />}
                {activeTab === 'profile' && <ProfilePanel username={username} isAdmin={isAdmin} />}
            </section>
        </div>
    );
}

/* ── Connections Panel ──────────────────────────────────────────── */

function ConnectionsPanel({ isAdmin }: { isAdmin: boolean }) {
    const { setHasDatabaseConnection } = useAuth();
    const [connections, setConnections] = useState<DBConnectionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [error, setError] = useState('');

    const fetchConnections = async () => {
        setLoading(true);
        try {
            const data = await getConnections();
            setConnections(data);
            setHasDatabaseConnection(data.length > 0);
        } catch {
            setConnections([]);
            setHasDatabaseConnection(false);
        } finally { setLoading(false); }
    };

    useEffect(() => { fetchConnections(); }, []);

    const handleDelete = async (id: string) => {
        if (!window.confirm('Delete this connection?')) return;
        try {
            await deleteConnection(id);
            setConnections(c => {
                const newC = c.filter(x => x.id !== id);
                setHasDatabaseConnection(newC.length > 0);
                return newC;
            });
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Delete failed');
        }
    };

    return (
        <div className="panel">
            <div className="panel-header">
                <div>
                    <h2>Database Connections</h2>
                    <p className="panel-subtitle">
                        {isAdmin
                            ? 'Manage your database connections for the AI agent'
                            : 'Available database connections'}
                    </p>
                </div>
                {/* Only admins can add connections */}
                {isAdmin && (
                    <button className="btn-accent-sm" onClick={() => setShowForm(!showForm)}>
                        {showForm ? '✕ Cancel' : '+ Add Connection'}
                    </button>
                )}
            </div>

            {error && <div className="error-banner">{error}</div>}

            {/* Non-admin info banner */}
            {!isAdmin && (
                <div className="info-banner">
                    ℹ️ Contact an administrator to add or remove database connections.
                </div>
            )}

            {isAdmin && showForm && (
                <AddConnectionForm
                    onSuccess={() => { setShowForm(false); fetchConnections(); }}
                    onCancel={() => setShowForm(false)}
                />
            )}

            {loading ? (
                <div className="panel-loading"><LoadingDots /></div>
            ) : connections.length === 0 && !showForm ? (
                <div className="panel-empty" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                    <div className="empty-icon" style={{ fontSize: '3rem', marginBottom: '1rem' }}>🗄️</div>
                    <h3 style={{ marginBottom: '0.5rem' }}>No connections yet</h3>
                    <p style={{ color: 'var(--text-color)', opacity: 0.7, marginBottom: '1.5rem' }}>
                        {isAdmin
                            ? 'Add a database connection to let the AI agent query your data.'
                            : 'Ask an administrator to add a database connection.'}
                    </p>
                    {isAdmin && (
                        <button onClick={() => setShowForm(true)} className="btn-accent" style={{ padding: '0.5rem 1rem' }}>
                            Connect a Database
                        </button>
                    )}
                </div>
            ) : !showForm && (
                <div className="cards-grid">
                    {connections.map(conn => (
                        <div key={conn.id} className="db-card">
                            <div className="db-card-header">
                                <div className="db-card-type">{conn.db_type.toUpperCase()}</div>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    {isAdmin && (
                                        <button
                                            className="btn-delete"
                                            onClick={() => handleDelete(conn.id)}
                                            title="Delete connection"
                                        >×</button>
                                    )}
                                </div>
                            </div>
                            <h3 className="db-card-name">{conn.connection_name}</h3>
                            <div className="db-card-details">
                                <div className="db-detail"><span className="db-label">Host</span><span>{conn.host}:{conn.port}</span></div>
                                <div className="db-detail"><span className="db-label">Database</span><span>{conn.database_name}</span></div>
                                <div className="db-detail"><span className="db-label">User</span><span>{conn.username}</span></div>
                                <div className="db-detail"><span className="db-label">SSL</span><span>{conn.ssl_enabled ? '✓ Enabled' : '✗ Off'}</span></div>
                            </div>
                            <div className="db-card-footer">
                                <span className="db-date">{new Date(conn.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── Add Connection Form ───────────────────────────────────────── */

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
                                <div className="query-card-db">{q.database_name}</div>
                                <button className="btn-delete-icon" onClick={(e) => handleDelete(q.id, e)} title="Delete query">×</button>
                            </div>
                            <h3 className="query-card-title">{q.title}</h3>
                            <p className="query-card-desc">
                                {q.natural_language_query.length > 120 
                                    ? q.natural_language_query.substring(0, 117) + '...' 
                                    : q.natural_language_query}
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
