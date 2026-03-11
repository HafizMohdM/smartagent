import { AuthProvider, useAuth } from './context/AuthContext';
import Header from './components/Header';
import LoginView from './views/LoginView';
import SetupView from './views/SetupView';
import ChatView from './views/ChatView';
import DashboardView from './views/DashboardView';

function AppContent() {
  const { currentView } = useAuth();

  return (
    <div className="app-root">
      <Header />
      <main className="app-main">
        {currentView === 'login' && <LoginView />}
        {currentView === 'setup' && <SetupView />}
        {currentView === 'chat' && <ChatView />}
        {currentView === 'dashboard' && <DashboardView />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
