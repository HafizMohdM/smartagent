import type { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Header from './components/Header';
import LoginView from './views/LoginView';
import ChatView from './views/ChatView';
import DashboardView from './views/DashboardView';

function PrivateRoute({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  return token ? <Navigate to="/dashboard" replace /> : <>{children}</>;
}

function AppContent() {
  return (
    <div className="app-root">
      <Header />
      <main className="app-main">
        <Routes>
          <Route path="/login" element={<PublicRoute><LoginView /></PublicRoute>} />
          <Route path="/dashboard" element={<PrivateRoute><DashboardView /></PrivateRoute>} />
          {/* Global chat — onboarding popup handled inside */}
          <Route path="/chat" element={<PrivateRoute><ChatView /></PrivateRoute>} />
          <Route path="/connections" element={<PrivateRoute><DashboardView /></PrivateRoute>} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}
