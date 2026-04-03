import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { setToken } from '../api/client';

const STORAGE_KEY = 'ai_agent_auth';

export type View = 'login' | 'chat' | 'dashboard';

function loadStoredAuth(): Partial<AuthState> {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return {};
        const { token, sessionId, username, hasDatabaseConnection, role } = JSON.parse(raw);
        if (token && sessionId) {
            setToken(token);
            return { token, sessionId, username, hasDatabaseConnection: hasDatabaseConnection ?? false, role: role ?? 'user' };
        }
    } catch { /* ignore */ }
    return {};
}

interface AuthState {
    token: string | null;
    sessionId: string | null;
    username: string | null;
    role: string | null;
    hasDatabaseConnection: boolean;
}

interface AuthContextValue extends AuthState {
    isAdmin: boolean;
    handleLoginSuccess: (token: string, sessionId: string, username: string, role: string) => void;
    setHasDatabaseConnection: (hasDb: boolean) => void;
    handleLogout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<AuthState>(() => ({
        token: null,
        sessionId: null,
        username: null,
        role: null,
        hasDatabaseConnection: false,
        ...loadStoredAuth(),
    }));

    // Update storage whenever auth state changes
    useEffect(() => {
        if (state.token && state.sessionId) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                token: state.token,
                sessionId: state.sessionId,
                username: state.username,
                hasDatabaseConnection: state.hasDatabaseConnection,
                role: state.role,
            }));
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }, [state]);

    // Listen for global auth errors (401) from the API client
    useEffect(() => {
        const onAuthError = () => handleLogout();
        window.addEventListener('auth_error', onAuthError);
        return () => window.removeEventListener('auth_error', onAuthError);
    }, []);

    const handleLoginSuccess = (token: string, sessionId: string, username: string, role: string) => {
        setToken(token);
        setState({ token, sessionId, username, role, hasDatabaseConnection: false });
    };

    const setHasDatabaseConnection = (hasDb: boolean) => {
        setState(s => ({ ...s, hasDatabaseConnection: hasDb }));
    };

    const handleLogout = () => {
        setToken(null);
        setState({ token: null, sessionId: null, username: null, role: null, hasDatabaseConnection: false });
    };

    const isAdmin = state.role === 'admin';

    return (
        <AuthContext.Provider value={{
            ...state,
            isAdmin,
            handleLoginSuccess,
            setHasDatabaseConnection,
            handleLogout,
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
