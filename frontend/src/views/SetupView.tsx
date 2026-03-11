import { useState, type FormEvent } from 'react';
import { connectDatabase } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingDots from '../components/LoadingDots';

export default function SetupView() {
    const { handleDbConnected, handleSkipDb } = useAuth();
    const [form, setForm] = useState({
        host: 'localhost',
        port: 5432,
        database: '',
        username: 'postgres',
        password: '',
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm(f => ({ ...f, [field]: field === 'port' ? Number(e.target.value) : e.target.value }));

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await connectDatabase(form);
            handleDbConnected();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Connection failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-card setup-card">
                <div className="auth-header">
                    <div className="logo-icon">🗄️</div>
                    <h1>Connect a Database</h1>
                    <p>Link a PostgreSQL database so the agent can query it</p>
                </div>

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="field-row">
                        <div className="field-group">
                            <label>Host</label>
                            <input type="text" value={form.host} onChange={set('host')} placeholder="localhost" required />
                        </div>
                        <div className="field-group field-small">
                            <label>Port</label>
                            <input type="number" value={form.port} onChange={set('port')} placeholder="5432" required />
                        </div>
                    </div>

                    <div className="field-group">
                        <label>Database Name</label>
                        <input type="text" value={form.database} onChange={set('database')} placeholder="mydb" required />
                    </div>

                    <div className="field-row">
                        <div className="field-group">
                            <label>Username</label>
                            <input type="text" value={form.username} onChange={set('username')} placeholder="postgres" required />
                        </div>
                        <div className="field-group">
                            <label>Password</label>
                            <input type="password" value={form.password} onChange={set('password')} placeholder="••••••••" required />
                        </div>
                    </div>

                    {error && <div className="error-banner">{error}</div>}

                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? <LoadingDots /> : 'Connect Database'}
                    </button>
                </form>

                <button className="btn-ghost" onClick={handleSkipDb}>
                    Skip for now — use without a database
                </button>
            </div>
        </div>
    );
}
