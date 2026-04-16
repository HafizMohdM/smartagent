import { useState, useEffect } from 'react';
import {
    getPendingUsers, approveUser, rejectUser,
    getAdminPendingConnections, adminApproveConnection, adminRejectConnection,
    type PendingUser, type DBConnectionItem,
} from '../api/client';
import LoadingDots from '../components/LoadingDots';

type Tab = 'users' | 'connections';

// ── Role badge ────────────────────────────────────────────────────
function RoleBadge({ role }: { role: string }) {
    const map: Record<string, { bg: string; color: string }> = {
        manager: { bg: 'rgba(99,102,241,0.1)',  color: '#6366f1' },
        user:    { bg: 'rgba(16,185,129,0.1)',  color: '#059669' },
        admin:   { bg: 'rgba(245,158,11,0.1)',  color: '#d97706' },
    };
    const s = map[role] ?? map.user;
    return (
        <span style={{ background: s.bg, color: s.color, fontSize: '0.7rem', fontWeight: 700,
                       padding: '2px 8px', borderRadius: '20px', textTransform: 'uppercase',
                       letterSpacing: '0.05em' }}>
            {role}
        </span>
    );
}

// ── Approve / Reject buttons ──────────────────────────────────────
function ActionButtons({ id, busy, onApprove, onReject }: {
    id: string; busy: string | null;
    onApprove: (id: string) => void;
    onReject:  (id: string) => void;
}) {
    return (
        <div style={{ display: 'flex', gap: '8px' }}>
            <button
                onClick={() => onApprove(id)}
                disabled={!!busy}
                style={{ padding: '5px 14px', background: 'rgba(16,185,129,0.1)',
                         border: '1px solid rgba(16,185,129,0.3)', borderRadius: '6px',
                         color: '#059669', fontWeight: 600, fontSize: '0.8rem',
                         cursor: busy ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
                {busy === id + '_a' ? '…' : '✓ Approve'}
            </button>
            <button
                onClick={() => onReject(id)}
                disabled={!!busy}
                style={{ padding: '5px 14px', background: 'rgba(239,68,68,0.08)',
                         border: '1px solid rgba(239,68,68,0.25)', borderRadius: '6px',
                         color: '#dc2626', fontWeight: 600, fontSize: '0.8rem',
                         cursor: busy ? 'not-allowed' : 'pointer', fontFamily: 'inherit' }}>
                {busy === id + '_r' ? '…' : '✕ Reject'}
            </button>
        </div>
    );
}

// ── Users tab ─────────────────────────────────────────────────────
function PendingUsersTab() {
    const [users, setUsers]   = useState<PendingUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy]     = useState<string | null>(null);
    const [error, setError]   = useState('');

    const load = async () => {
        setLoading(true);
        try { setUsers(await getPendingUsers()); }
        catch (e: any) { setError(e.message); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const handle = async (id: string, action: 'approve' | 'reject') => {
        setBusy(id + (action === 'approve' ? '_a' : '_r'));
        try {
            const updated = action === 'approve' ? await approveUser(id) : await rejectUser(id);
            setUsers(prev => prev.filter(u => u.id !== updated.id));
        } catch (e: any) { setError(e.message); }
        finally { setBusy(null); }
    };

    if (loading) return <div style={{ padding: '40px', textAlign: 'center' }}><LoadingDots /></div>;

    return (
        <div>
            {error && <div className="error-banner" style={{ marginBottom: '16px' }}>⚠️ {error}</div>}
            {users.length === 0 ? (
                <div className="approvals-empty">
                    <span>✅</span>
                    <p>No pending user registrations</p>
                </div>
            ) : (
                <div className="approvals-list">
                    {users.map(u => (
                        <div key={u.id} className="approval-card">
                            <div className="approval-card-info">
                                <div className="approval-card-name">
                                    {u.name || u.email}
                                    <RoleBadge role={u.role} />
                                </div>
                                <div className="approval-card-meta">
                                    {u.email} · Registered {new Date(u.created_at).toLocaleDateString()}
                                </div>
                            </div>
                            <ActionButtons id={u.id} busy={busy}
                                onApprove={id => handle(id, 'approve')}
                                onReject={id  => handle(id, 'reject')} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Connections tab ───────────────────────────────────────────────
function PendingConnectionsTab() {
    const [conns, setConns]   = useState<DBConnectionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy]     = useState<string | null>(null);
    const [error, setError]   = useState('');

    const load = async () => {
        setLoading(true);
        try { setConns(await getAdminPendingConnections()); }
        catch (e: any) { setError(e.message); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const handle = async (id: string, action: 'approve' | 'reject') => {
        setBusy(id + (action === 'approve' ? '_a' : '_r'));
        try {
            const updated = action === 'approve'
                ? await adminApproveConnection(id)
                : await adminRejectConnection(id);
            setConns(prev => prev.filter(c => c.id !== updated.id));
        } catch (e: any) { setError(e.message); }
        finally { setBusy(null); }
    };

    if (loading) return <div style={{ padding: '40px', textAlign: 'center' }}><LoadingDots /></div>;

    return (
        <div>
            {error && <div className="error-banner" style={{ marginBottom: '16px' }}>⚠️ {error}</div>}
            {conns.length === 0 ? (
                <div className="approvals-empty">
                    <span>✅</span>
                    <p>No pending connection requests</p>
                </div>
            ) : (
                <div className="approvals-list">
                    {conns.map(c => (
                        <div key={c.id} className="approval-card">
                            <div className="approval-card-info">
                                <div className="approval-card-name">
                                    {c.connection_name}
                                    <span style={{ background: 'rgba(99,102,241,0.1)', color: '#6366f1',
                                                   fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px',
                                                   borderRadius: '20px', textTransform: 'uppercase' }}>
                                        {c.db_type}
                                    </span>
                                </div>
                                <div className="approval-card-meta">
                                    {c.host}:{c.port} / {c.database_name} · {new Date(c.created_at).toLocaleDateString()}
                                </div>
                            </div>
                            <ActionButtons id={c.id} busy={busy}
                                onApprove={id => handle(id, 'approve')}
                                onReject={id  => handle(id, 'reject')} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Main view ─────────────────────────────────────────────────────
export default function ApprovalsView() {
    const [tab, setTab] = useState<Tab>('users');

    return (
        <div className="panel animate-in">
            <div className="panel-header">
                <div>
                    <h2>Approvals</h2>
                    <p className="panel-subtitle">Review and approve pending user registrations and connection requests</p>
                </div>
            </div>

            <div className="approvals-tabs">
                <button className={`approvals-tab ${tab === 'users' ? 'active' : ''}`}
                        onClick={() => setTab('users')}>
                    👤 Users
                </button>
                <button className={`approvals-tab ${tab === 'connections' ? 'active' : ''}`}
                        onClick={() => setTab('connections')}>
                    🗄️ Connections
                </button>
            </div>

            <div style={{ marginTop: '20px' }}>
                {tab === 'users'       ? <PendingUsersTab />       : <PendingConnectionsTab />}
            </div>
        </div>
    );
}
