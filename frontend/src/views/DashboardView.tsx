import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
    getConnections, createConnection, deleteConnection,
    getSavedQueries, deleteSavedQuery,
    type DBConnectionItem, type SavedQueryItem
} from '../api/client';
import LoadingDots from '../components/LoadingDots';

type Tab = 'connections' | 'queries' | 'profile';

export default function DashboardView() {
    const { username, isAdmin } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<Tab>('connections');

    return (
        <div className="dashboard-layout">
            <aside className="dashboard-sidebar">
                <div className="sidebar-title">Dashboard</div>
                <nav className="sidebar-nav">
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
                        className={`sidebar-item ${activeTab === 'profile' ? 'sidebar-active' : ''}`}
                        onClick={() => setActiveTab('profile')}
                    >
                        <span className="sidebar-icon">👤</span>
                        <span>Profile</span>
                    </button>
                </nav>
                {/* Chat shortcut always visible */}
                <div style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', marginTop: 'auto' }}>
                    <button
                        id="open-chat-btn"
                        className="btn-accent"
                        style={{ width: '100%', padding: '0.6rem' }}
                        onClick={() => navigate('/chat')}
                    >
                        💬 Open Chat
                    </button>
                </div>
            </aside>
            <section className="dashboard-content">
                {activeTab === 'connections' && <ConnectionsPanel isAdmin={isAdmin} />}
                {activeTab === 'queries' && <QueriesPanel />}
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
    const [expanded, setExpanded] = useState<string | null>(null);
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

    const handleDelete = async (id: string) => {
        try {
            await deleteSavedQuery(id);
            setQueries(q => q.filter(x => x.id !== id));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Delete failed');
        }
    };

    const handleRun = (nlQuery: string) => {
        navigate('/chat', { state: { prefillQuery: nlQuery } });
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
                <div className="queries-list">
                    {queries.map(q => (
                        <div key={q.id} className={`query-card ${expanded === q.id ? 'query-expanded' : ''}`}>
                            <div className="query-header" onClick={() => setExpanded(expanded === q.id ? null : q.id)}>
                                <div className="query-info">
                                    <h3>{q.query_name}</h3>
                                    <p className="query-nl">{q.natural_language_query}</p>
                                </div>
                                <div className="query-meta">
                                    {q.row_count != null && <span className="query-stat">{q.row_count} rows</span>}
                                    {q.execution_time_ms != null && <span className="query-stat">{q.execution_time_ms}ms</span>}
                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        <button 
                                            className="btn-accent-sm" 
                                            style={{ padding: '2px 10px', fontSize: '0.75rem' }}
                                            onClick={(e) => { e.stopPropagation(); handleRun(q.natural_language_query); }}
                                        >
                                            ▶ Run
                                        </button>
                                        <button className="btn-delete" onClick={(e) => { e.stopPropagation(); handleDelete(q.id); }} title="Delete">×</button>
                                    </div>
                                </div>
                            </div>
                            {expanded === q.id && (
                                <div className="query-details">
                                    <div className="sql-block">
                                        <div className="sql-label">Generated SQL</div>
                                        <pre className="sql-code">{q.generated_sql}</pre>
                                    </div>
                                    <div className="query-footer">
                                        <span className="db-date">Saved {new Date(q.created_at).toLocaleString()}</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── Profile Panel ─────────────────────────────────────────────── */

function ProfilePanel({ username, isAdmin }: { username: string | null; isAdmin: boolean }) {
    return (
        <div className="panel">
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
        </div>
    );
}
