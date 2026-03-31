import { useAuth } from '../context/AuthContext';
import { logout } from '../api/client';

export default function Header() {
    const { username, dbConnected, currentView, handleLogout, handleGoToDashboard, handleGoToChat } = useAuth();

    const handleLogoutClick = async () => {
        try { await logout(); } catch { /* ignore */ }
        handleLogout();
    };

    if (currentView === 'login') return null;

    return (
        <header className="app-header">
            <div className="header-brand">
                <span className="header-logo">⚡</span>
                <span className="header-title">AI Agent Platform</span>
            </div>

            <div className="header-status">
                {(currentView === 'chat' || currentView === 'dashboard') && (
                    <div className="header-nav">
                        <button
                            className={`nav-btn ${currentView === 'chat' ? 'nav-btn-active' : ''}`}
                            onClick={handleGoToChat}
                        >
                            💬 Chat
                        </button>
                        <button
                            className={`nav-btn ${currentView === 'dashboard' ? 'nav-btn-active' : ''}`}
                            onClick={handleGoToDashboard}
                        >
                            📊 Dashboard
                        </button>
                    </div>
                )}

                {currentView === 'chat' && (
                    <div className={`status-badge ${dbConnected ? 'status-connected' : 'status-idle'}`}>
                        <span className="status-dot" />
                        {dbConnected ? 'DB Connected' : 'No Database'}
                    </div>
                )}

                <span className="header-user">👤 {username}</span>
                
                {/* Hide logout button if we are embedded in an iframe (SSO) */}
                {window.self === window.top && (
                    <button id="logout-btn" className="btn-logout" onClick={handleLogoutClick}>
                        Logout
                    </button>
                )}
            </div>
        </header>
    );
}
