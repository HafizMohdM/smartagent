import { useState, useEffect, type FormEvent } from 'react';
import { useAuth } from '../context/AuthContext';
import {
    getConnections, createConnection, deleteConnection,
    getSavedQueries, deleteSavedQuery,
    type DBConnectionItem, type SavedQueryItem
} from '../api/client';
import LoadingDots from '../components/LoadingDots';

type Tab = 'connections' | 'queries' | 'profile';

export default function DashboardView() {
    const { username, handleGoToSetup } = useAuth();
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
                <div className="sidebar-footer">
                    <button className="btn-ghost-sm" onClick={handleGoToSetup}>
                        + Quick Connect DB
                    </button>
                </div>
            </aside>
            <section className="dashboard-content">
                {activeTab === 'connections' && <ConnectionsPanel />}
                {activeTab === 'queries' && <QueriesPanel />}
                {activeTab === 'profile' && <ProfilePanel username={username} />}
            </section>
        </div>
    );
}

/* ── Connections Panel ──────────────────────────────────────────── */

function ConnectionsPanel() {
    const [connections, setConnections] = useState<DBConnectionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [error, setError] = useState('');

    const fetchConnections = async () => {
        setLoading(true);
        try {
            const data = await getConnections();
            setConnections(data);
        } catch { setConnections([]); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchConnections(); }, []);

    const handleDelete = async (id: string) => {
        try {
            await deleteConnection(id);
            setConnections(c => c.filter(x => x.id !== id));
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Delete failed');
        }
    };

    return (
        <div className="panel">
            <div className="panel-header">
                <div>
                    <h2>Database Connections</h2>
                    <p className="panel-subtitle">Manage your database connections for the AI agent</p>
                </div>
                <button className="btn-accent-sm" onClick={() => setShowForm(!showForm)}>
                    {showForm ? '✕ Cancel' : '+ Add Connection'}
                </button>
            </div>

            {error && <div className="error-banner">{error}</div>}

            {showForm && (
                <AddConnectionForm
                    onSuccess={() => { setShowForm(false); fetchConnections(); }}
                    onCancel={() => setShowForm(false)}
                />
            )}

            {loading ? (
                <div className="panel-loading"><LoadingDots /></div>
            ) : connections.length === 0 ? (
                <div className="panel-empty">
                    <div className="empty-icon">🗄️</div>
                    <h3>No connections yet</h3>
                    <p>Add a database connection to let the AI agent query your data.</p>
                </div>
            ) : (
                <div className="cards-grid">
                    {connections.map(conn => (
                        <div key={conn.id} className="db-card">
                            <div className="db-card-header">
                                <div className="db-card-type">{conn.db_type.toUpperCase()}</div>
                                <button className="btn-delete" onClick={() => handleDelete(conn.id)} title="Delete">×</button>
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
                                    <button className="btn-delete" onClick={(e) => { e.stopPropagation(); handleDelete(q.id); }} title="Delete">×</button>
                                </div>
                            </div>
                            {expanded === q.id && (
                                <div className="query-details">
                                    <div className="sql-block">
                                        <div className="sql-label">Generated SQL</div>
                                        <pre className="sql-code">{q.generated_sql}</pre>
                                    </div>
                                    {q.query_result_snapshot && q.query_result_snapshot.length > 0 && (
                                        <div className="result-snapshot">
                                            <div className="sql-label">Result Preview ({q.query_result_snapshot.length} rows)</div>
                                            <div className="snapshot-table-wrap">
                                                <table className="snapshot-table">
                                                    <thead>
                                                        <tr>
                                                            {Object.keys(q.query_result_snapshot[0] as Record<string, unknown>).map(k => (
                                                                <th key={k}>{k}</th>
                                                            ))}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {q.query_result_snapshot.slice(0, 10).map((row, i) => (
                                                            <tr key={i}>
                                                                {Object.values(row as Record<string, unknown>).map((v, j) => (
                                                                    <td key={j}>{String(v)}</td>
                                                                ))}
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}
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

function ProfilePanel({ username }: { username: string | null }) {
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
                    <span>👤</span>
                </div>
                <div className="profile-info">
                    <div className="profile-row">
                        <span className="profile-label">Email</span>
                        <span className="profile-value">{username ?? 'N/A'}</span>
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
