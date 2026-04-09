import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
    getSavedQuery, updateSavedQuery, deleteSavedQuery,
    type SavedQueryItem 
} from '../api/client';
import LoadingDots from '../components/LoadingDots';

export default function SavedQueryDetailView() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    
    const [query, setQuery] = useState<SavedQueryItem | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    
    // UI States
    const [showSql, setShowSql] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState('');
    const [editSql, setEditSql] = useState('');
    const [saving, setSaving] = useState(false);
    const [executing, setExecuting] = useState(false);

    const fetchData = async () => {
        if (!id) return;
        setExecuting(true);
        setError('');
        try {
            const data = await getSavedQuery(id);
            setQuery(data);
            setEditTitle(data.title);
            setEditSql(data.query);
        } catch (err: any) {
            setError(err.message || 'Failed to fetch query details');
        } finally {
            setLoading(false);
            setExecuting(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [id]);

    const handleSave = async () => {
        if (!id || !query) return;
        setSaving(true);
        setError('');
        try {
            const updated = await updateSavedQuery(id, { 
                title: editTitle,
                query: editSql
            });
            setQuery(updated);
            setIsEditing(false);
        } catch (err: any) {
            setError(err.message || 'Failed to save changes');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!id || !window.confirm('Are you sure you want to delete this saved query?')) return;
        try {
            await deleteSavedQuery(id);
            navigate('/dashboard');
        } catch (err: any) {
            setError(err.message || 'Delete failed');
        }
    };

    const handleRun = () => {
        fetchData(); // Re-executes because getSavedQuery points to /preview
    };

    if (loading) return <div className="panel-loading"><LoadingDots /></div>;
    if (error && !query) return <div className="error-banner" style={{ margin: '2rem' }}>{error}</div>;
    if (!query) return <div className="panel-empty">Query not found</div>;

    const results = query.query_result_snapshot;
    const rows = Array.isArray(results) ? results : (results?.data || results?.rows || []);
    const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

    return (
        <div className="detail-view animate-in">
            <header className="detail-header">
                <div className="detail-header-left">
                    <Link to="/dashboard" className="btn-back">← Back</Link>
                    {isEditing ? (
                        <input 
                            className="edit-title-input"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            autoFocus
                        />
                    ) : (
                        <h1>{query.title}</h1>
                    )}
                </div>
                <div className="detail-actions">
                    {isEditing ? (
                        <>
                            <button className="btn-ghost-sm" onClick={() => setIsEditing(false)}>Cancel</button>
                            <button className="btn-accent-sm" onClick={handleSave} disabled={saving}>
                                {saving ? 'Saving...' : 'Save Changes'}
                            </button>
                        </>
                    ) : (
                        <>
                            <button className="btn-ghost-sm" onClick={() => setIsEditing(true)}>Edit</button>
                            <button className="btn-delete-sm" onClick={handleDelete}>Delete</button>
                            <button className="btn-accent-sm" onClick={handleRun} disabled={executing}>
                                {executing ? <LoadingDots /> : '▶ Run Query'}
                            </button>
                        </>
                    )}
                </div>
            </header>

            <div className="detail-content">
                <div className="detail-meta-strip">
                    <div className="meta-item">
                        <span className="meta-label">Database</span>
                        <span className="meta-value">🗄️ {query.database_name}</span>
                    </div>
                    <div className="meta-item">
                        <span className="meta-label">Created By</span>
                        <span className="meta-value">👤 {query.username}</span>
                    </div>
                    <div className="meta-item">
                        <span className="meta-label">Date</span>
                        <span className="meta-value">{new Date(query.created_at).toLocaleDateString()}</span>
                    </div>
                    {query.row_count !== null && (
                        <div className="meta-item">
                            <span className="meta-label">Rows</span>
                            <span className="meta-value">{query.row_count}</span>
                        </div>
                    )}
                </div>

                <div className="sql-section">
                    <div className="sql-header">
                        <h3>SQL Query</h3>
                        <button className="btn-link" onClick={() => setShowSql(!showSql)}>
                            {showSql ? 'Hide SQL' : 'View SQL'}
                        </button>
                    </div>
                    
                    {(showSql || isEditing) && (
                        <div className="sql-box">
                            {isEditing ? (
                                <textarea 
                                    className="edit-sql-textarea"
                                    value={editSql}
                                    onChange={(e) => setEditSql(e.target.value)}
                                />
                            ) : (
                                <pre><code>{query.query}</code></pre>
                            )}
                        </div>
                    )}
                </div>

                <div className="results-section">
                    <div className="section-header">
                        <h3>Query Results</h3>
                        {executing && <LoadingDots />}
                    </div>

                    {error && <div className="error-banner" style={{ marginBottom: '1rem' }}>{error}</div>}

                    <div className="table-wrapper">
                        {rows.length > 0 ? (
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        {columns.map(col => <th key={col}>{col}</th>)}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row: any, i: number) => (
                                        <tr key={i}>
                                            {columns.map(col => (
                                                <td key={col}>
                                                    {row[col] === null ? <span className="null-val">null</span> : String(row[col])}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : !executing && (
                            <div className="empty-results">No data returned or query has not been run.</div>
                        )}
                    </div>
                </div>
            </div>
            
            <style>{`
                .detail-view { padding: 2rem; max-width: 1200px; margin: 0 auto; height: 100%; display: flex; flex-direction: column; }
                .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; gap: 2rem; }
                .detail-header-left { display: flex; align-items: center; gap: 1.5rem; flex: 1; }
                .detail-header h1 { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); letter-spacing: -0.02em; }
                .edit-title-input { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); width: 100%; background: var(--bg-elevated); border: 1px solid var(--accent); border-radius: 8px; padding: 4px 12px; outline: none; }
                
                .btn-back { color: var(--text-secondary); text-decoration: none; font-weight: 500; font-size: 0.9rem; transition: color 0.2s; }
                .btn-back:hover { color: var(--accent); }
                
                .detail-actions { display: flex; gap: 0.75rem; }
                .btn-delete-sm { background: rgba(239, 68, 68, 0.08); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2); padding: 6px 14px; border-radius: 8px; font-size: 0.85rem; font-weight: 500; cursor: pointer; }
                .btn-delete-sm:hover { background: #ef4444; color: white; }
                
                .detail-content { flex: 1; display: flex; flex-direction: column; gap: 1.5rem; overflow: hidden; }
                
                .detail-meta-strip { display: flex; gap: 2rem; padding: 1rem 1.5rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; }
                .meta-item { display: flex; flex-direction: column; gap: 4px; }
                .meta-label { font-size: 0.7rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
                .meta-value { font-size: 0.9rem; font-weight: 500; color: var(--text-secondary); }
                
                .sql-section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
                .sql-header { padding: 0.75rem 1.25rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); background: rgba(0,0,0,0.01); }
                .sql-header h3 { font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
                .btn-link { background: none; border: none; color: var(--accent); font-size: 0.8rem; font-weight: 500; cursor: pointer; }
                .sql-box { padding: 1.25rem; background: #1e293b; color: #f8fafc; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; line-height: 1.6; }
                .sql-box pre { margin: 0; white-space: pre-wrap; word-break: break-all; }
                .edit-sql-textarea { width: 100%; min-height: 150px; background: transparent; color: white; border: none; outline: none; font-family: inherit; resize: vertical; }
                
                .results-section { flex: 1; background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
                .section-header { padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 1rem; }
                .section-header h3 { font-size: 1rem; font-weight: 600; color: var(--text-primary); }
                
                .table-wrapper { flex: 1; overflow: auto; }
                .data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
                .data-table th { position: sticky; top: 0; background: var(--bg-elevated); padding: 10px 14px; text-align: left; font-weight: 600; color: var(--text-secondary); border-bottom: 1px solid var(--border); z-index: 1; }
                .data-table td { padding: 10px 14px; border-bottom: 1px solid var(--border); color: var(--text-primary); }
                .null-val { font-style: italic; color: var(--text-muted); opacity: 0.6; }
                .empty-results { padding: 3rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }
                
                @media (max-width: 768px) {
                    .detail-header { flex-direction: column; align-items: flex-start; gap: 1rem; }
                    .detail-meta-strip { flex-wrap: wrap; gap: 1rem; }
                }
            `}</style>
        </div>
    );
}
