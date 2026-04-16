import { useState, type FormEvent } from 'react';
import { login, register } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingDots from '../components/LoadingDots';

export default function LoginView() {
    const { handleLoginSuccess } = useAuth();
    const [isRegister, setIsRegister] = useState(false);
    const [email, setEmail]       = useState('');
    const [password, setPassword] = useState('');
    const [name, setName]         = useState('');
    const [role, setRole]         = useState<'user' | 'manager'>('user');
    const [error, setError]       = useState('');
    const [success, setSuccess]   = useState('');
    const [loading, setLoading]   = useState(false);

    const doLogin = async (emailOrUser: string, pwd: string) => {
        setError(''); setSuccess('');
        setLoading(true);
        try {
            const res = await login(emailOrUser, pwd);
            handleLoginSuccess(res.access_token, res.session_id, emailOrUser, res.role);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Login failed');
        } finally { setLoading(false); }
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError(''); setSuccess('');

        if (isRegister) {
            setLoading(true);
            try {
                await register({ name: name || undefined, email, password, role });
                setSuccess('Account created! Your request is pending admin approval. You will be notified once approved.');
                setIsRegister(false);
                setEmail(''); setPassword(''); setName('');
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : 'Registration failed');
            } finally { setLoading(false); }
            return;
        }
        await doLogin(email, password);
    };

    return (
        <div className="auth-container">
            <div className="auth-card">
                <div className="auth-header">
                    <div className="logo-icon">✨</div>
                    <h1>SmartAgent</h1>
                    <p>{isRegister ? 'Create your account' : 'Sign in to your account'}</p>
                </div>

                <form onSubmit={handleSubmit} className="auth-form">
                    {isRegister && (
                        <>
                            <div className="field-group">
                                <label htmlFor="name">Full Name</label>
                                <input id="name" type="text" placeholder="John Doe"
                                       value={name} onChange={e => setName(e.target.value)} />
                            </div>
                            <div className="field-group">
                                <label htmlFor="role">Role</label>
                                <select id="role" value={role}
                                        onChange={e => setRole(e.target.value as 'user' | 'manager')}
                                        style={{ width: '100%', padding: '10px 12px', borderRadius: '8px',
                                                 border: '1px solid var(--border)', fontFamily: 'inherit',
                                                 fontSize: '0.9rem', background: 'var(--bg-elevated)' }}>
                                    <option value="user">User — view & query data</option>
                                    <option value="manager">Manager — create & manage connections</option>
                                </select>
                            </div>
                        </>
                    )}

                    <div className="field-group">
                        <label htmlFor="email">Email</label>
                        <input id="email" type="text"
                               placeholder={isRegister ? 'you@company.com' : 'Email or username'}
                               value={email} onChange={e => setEmail(e.target.value)}
                               required autoFocus />
                    </div>

                    <div className="field-group">
                        <label htmlFor="password">Password</label>
                        <input id="password" type="password" placeholder="••••••••"
                               value={password} onChange={e => setPassword(e.target.value)}
                               required minLength={isRegister ? 6 : undefined} />
                    </div>

                    {isRegister && (
                        <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)',
                                      borderRadius: '8px', padding: '10px 14px', fontSize: '0.82rem',
                                      color: '#92400e', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                            <span>⏳</span>
                            <span>Your account will require <strong>admin approval</strong> before you can log in.</span>
                        </div>
                    )}

                    {error   && <div className="error-banner">{error}</div>}
                    {success && (
                        <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)',
                                      borderRadius: '8px', padding: '10px 14px', fontSize: '0.82rem', color: '#065f46' }}>
                            ✓ {success}
                        </div>
                    )}

                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? <LoadingDots /> : (isRegister ? 'Request Access' : 'Sign In')}
                    </button>
                </form>

                {/* Admin quick-login only */}
                {!isRegister && (
                    <div className="quick-login-section">
                        <div className="quick-login-label">Admin Access</div>
                        <div className="quick-login-buttons">
                            <button
                                className="quick-login-btn quick-login-admin"
                                onClick={() => doLogin('admin', 'admin123')}
                                disabled={loading}
                                title="Login as Admin"
                            >
                                <span className="quick-login-icon">🛡️</span>
                                <div>
                                    <div className="quick-login-role">Admin</div>
                                    <div className="quick-login-hint">admin / admin123</div>
                                </div>
                            </button>
                        </div>
                    </div>
                )}

                <button className="btn-ghost"
                        onClick={() => { setIsRegister(!isRegister); setError(''); setSuccess(''); }}>
                    {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Request Access"}
                </button>
            </div>
        </div>
    );
}
