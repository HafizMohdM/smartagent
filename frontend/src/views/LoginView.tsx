import { useState, type FormEvent } from 'react';
import { login, register } from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingDots from '../components/LoadingDots';

export default function LoginView() {
    const { handleLoginSuccess } = useAuth();
    const [isRegister, setIsRegister] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [phone, setPhone] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const doLogin = async (emailOrUser: string, pwd: string) => {
        setError('');
        setLoading(true);
        try {
            const res = await login(emailOrUser, pwd);
            handleLoginSuccess(res.access_token, res.session_id, emailOrUser, res.role);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        if (isRegister) {
            setError('');
            setLoading(true);
            try {
                await register({ name: name || undefined, email, phone_number: phone || undefined, password });
                const res = await login(email, password);
                handleLoginSuccess(res.access_token, res.session_id, email, res.role);
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : 'Registration failed');
            } finally {
                setLoading(false);
            }
            return;
        }
        await doLogin(email, password);
    };

    return (
        <div className="auth-container">
            <div className="auth-card">
                <div className="auth-header">
                    <div className="logo-icon">⚡</div>
                    <h1>AI Agent Platform</h1>
                    <p>{isRegister ? 'Create your account' : 'Sign in to start your session'}</p>
                </div>

                <form onSubmit={handleSubmit} className="auth-form">
                    {isRegister && (
                        <>
                            <div className="field-group">
                                <label htmlFor="name">Full Name</label>
                                <input
                                    id="name"
                                    type="text"
                                    placeholder="John Doe"
                                    value={name}
                                    onChange={e => setName(e.target.value)}
                                />
                            </div>
                            <div className="field-group">
                                <label htmlFor="phone">Phone Number</label>
                                <input
                                    id="phone"
                                    type="tel"
                                    placeholder="+1 234 567 8900"
                                    value={phone}
                                    onChange={e => setPhone(e.target.value)}
                                />
                            </div>
                        </>
                    )}

                    <div className="field-group">
                        <label htmlFor="email">Email</label>
                        <input
                            id="email"
                            type="text"
                            placeholder="admin@admin.local or admin"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>

                    <div className="field-group">
                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            placeholder="••••••••"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            required
                            minLength={isRegister ? 6 : undefined}
                        />
                    </div>

                    {error && <div className="error-banner">{error}</div>}

                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? <LoadingDots /> : (isRegister ? 'Create Account' : 'Sign In')}
                    </button>
                </form>

                {!isRegister && (
                    <div className="quick-login-section">
                        <div className="quick-login-label">Quick Login</div>
                        <div className="quick-login-buttons">
                            <button
                                id="quick-login-admin"
                                className="quick-login-btn quick-login-admin"
                                onClick={() => doLogin('admin', 'admin123')}
                                disabled={loading}
                                title="Login as Admin (full access)"
                            >
                                <span className="quick-login-icon">🛡️</span>
                                <div>
                                    <div className="quick-login-role">Admin</div>
                                    <div className="quick-login-hint">admin / admin123</div>
                                </div>
                            </button>
                            <button
                                id="quick-login-user"
                                className="quick-login-btn quick-login-user"
                                onClick={() => doLogin('user', 'user123')}
                                disabled={loading}
                                title="Login as regular User"
                            >
                                <span className="quick-login-icon">👤</span>
                                <div>
                                    <div className="quick-login-role">User</div>
                                    <div className="quick-login-hint">user / user123</div>
                                </div>
                            </button>
                        </div>
                    </div>
                )}

                <button
                    className="btn-ghost"
                    onClick={() => { setIsRegister(!isRegister); setError(''); }}
                >
                    {isRegister ? 'Already have an account? Sign In' : "Don't have an account? Register"}
                </button>
            </div>
        </div>
    );
}
