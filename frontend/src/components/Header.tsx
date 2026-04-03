import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { logout } from '../api/client';

export default function Header() {
    const { username, handleLogout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const isLoginPage = location.pathname === '/login';

    const handleLogoutClick = async () => {
        try { await logout(); } catch { /* ignore */ }
        handleLogout();
        navigate('/login');
    };

    if (isLoginPage || !username) return null;

    return (
        <header className="app-header">
            <div className="header-brand" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>
                <span className="header-logo">⚡</span>
                <span className="header-title">AI Agent Platform</span>
            </div>

            <div className="header-status">
                <div className="header-nav">
                    <button
                        className={`nav-btn ${location.pathname.startsWith('/chat') ? 'nav-btn-active' : ''}`}
                        onClick={() => navigate('/dashboard')} // Chat takes context, so default to dashboard if they click "Chat" generally? 
                                                              // Or hide it if not in a connection?
                                                              // For now, let's just let them go to dashboard to pick a connection.
                    >
                        📊 Connections
                    </button>
                    <button
                        className={`nav-btn ${location.pathname === '/dashboard' ? 'nav-btn-active' : ''}`}
                        onClick={() => navigate('/dashboard')}
                    >
                        🏠 Dashboard
                    </button>
                </div>

                <div className="header-user-info" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <span className="header-user">👤 {username}</span>
                    <button id="logout-btn" className="btn-logout" onClick={handleLogoutClick}>
                        Logout
                    </button>
                </div>
            </div>
        </header>
    );
}
