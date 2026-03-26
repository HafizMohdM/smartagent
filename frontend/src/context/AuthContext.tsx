import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { setToken, setSessionId } from '../api/client';

const STORAGE_KEY = 'ai_agent_auth';

export type View = 'login' | 'setup' | 'chat' | 'dashboard';

function loadStoredAuth(): Partial<AuthState> {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return {};
        const { token, sessionId, username, dbConnected } = JSON.parse(raw);
        if (token && sessionId) {
            setToken(token);
            setSessionId(sessionId);
            return { token, sessionId, username, dbConnected: dbConnected ?? false, currentView: 'chat' };
        }
    } catch { /* ignore */ }
    return {};
}

interface AuthState {
    token: string | null;
    sessionId: string | null;
    username: string | null;
    dbConnected: boolean;
    currentView: View;
}

interface AuthContextValue extends AuthState {
    handleLoginSuccess: (token: string, sessionId: string, username: string) => void;
    handleDbConnected: () => void;
    handleSkipDb: () => void;
    handleLogout: () => void;
    handleGoToDashboard: () => void;
    handleGoToChat: () => void;
    handleGoToSetup: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<AuthState>(() => ({
        token: null,
        sessionId: null,
        username: null,
        dbConnected: false,
        currentView: 'login',
        ...loadStoredAuth(),
    }));

    // Update storage whenever auth state changes
    useEffect(() => {
        if (state.token && state.sessionId) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                token: state.token,
                sessionId: state.sessionId,
                username: state.username,
                dbConnected: state.dbConnected,
            }));
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }, [state]);

    // Listen for global auth errors (401, 404) from the API client
    useEffect(() => {
        const onAuthError = () => handleLogout();
        window.addEventListener('auth_error', onAuthError);
        return () => window.removeEventListener('auth_error', onAuthError);
    }, []);

    // Intercept token and sessionId from URL for iframe integration
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const urlToken = params.get('token');
        const urlSessionId = params.get('sessionId');
        const urlView = params.get('view') as View;
        
        if (urlToken) {
            setToken(urlToken);
            const sid = urlSessionId || (Math.random().toString(36).substring(2) + Date.now().toString(36));
            setSessionId(sid);
            setState(s => ({ 
                ...s,
                token: urlToken, 
                sessionId: sid, 
                username: params.get('username') || 'HRMS User',
                dbConnected: true, // Auto-connect for iframe
                currentView: urlView || 'chat'
            }));
            
            // Clean up URL parameters to keep it clean
            const newUrl = window.location.pathname;
            window.history.replaceState({}, document.title, newUrl);
        }
    }, []);

    const handleLoginSuccess = (token: string, sessionId: string, username: string) => {
        setToken(token);
        setSessionId(sessionId);
        setState({ token, sessionId, username, dbConnected: false, currentView: 'setup' });
    };

    const handleDbConnected = () => {
        setState(s => ({ ...s, dbConnected: true, currentView: 'chat' }));
    };

    const handleSkipDb = () => {
        setState(s => ({ ...s, currentView: 'chat' }));
    };

    const handleLogout = () => {
        setToken(null);
        setSessionId(null);
        setState({ token: null, sessionId: null, username: null, dbConnected: false, currentView: 'login' });
    };

    const handleGoToDashboard = () => {
        setState(s => ({ ...s, currentView: 'dashboard' }));
    };

    const handleGoToChat = () => {
        setState(s => ({ ...s, currentView: 'chat' }));
    };

    const handleGoToSetup = () => {
        setState(s => ({ ...s, currentView: 'setup' }));
    };

    return (
        <AuthContext.Provider value={{
            ...state,
            handleLoginSuccess,
            handleDbConnected,
            handleSkipDb,
            handleLogout,
            handleGoToDashboard,
            handleGoToChat,
            handleGoToSetup,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}
