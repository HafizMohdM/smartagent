import { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { logout } from '../api/client';

export default function Header() {
    const { username, handleLogout, isAdmin } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const isLoginPage = location.pathname === '/login';
    const isLandingPage = location.pathname === '/landing';

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, []);

    const handleLogoutClick = () => {
        logout().catch(() => { });
        handleLogout();
        navigate('/login');
    };

    if (isLoginPage || isLandingPage || !username) return null;

    // Get initials for avatar
    const initials = username
        ? username.split('@')[0].slice(0, 2).toUpperCase()
        : 'U';

    const isOnDashboard = location.pathname === '/dashboard' || location.pathname === '/';
    const isOnChat = location.pathname.startsWith('/chat');
    const isOnBuilder = location.pathname.startsWith('/builder');

    return (
        <header className="app-header">
            {/* Left: Brand */}
            <div className="header-brand" onClick={() => navigate('/dashboard')}>
                <div className="header-logo-mark" style={{ background: 'linear-gradient(135deg, #6F1D1B, #99582A)' }}>✨</div>
                <span className="header-title" style={{ fontFamily: "'Playfair Display', serif" }}>cognivelt AI</span>
            </div>

            {/* Mobile Menu Toggle */}
            <button
                className="mobile-menu-toggle"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                aria-label="Toggle navigation"
            >
                ☰
            </button>

            {/* Center: Nav */}
            <nav className={`nav-center ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
                <button
                    className={`nav-item ${isOnDashboard ? 'active' : ''}`}
                    onClick={() => { navigate('/dashboard'); setIsMobileMenuOpen(false); }}
                >
                    Dashboard
                </button>
                <button
                    className={`nav-item ${isOnChat ? 'active' : ''}`}
                    onClick={() => { navigate('/chat'); setIsMobileMenuOpen(false); }}
                >
                    Chat
                </button>
                {isAdmin && (
                    <button
                        className={`nav-item ${isOnBuilder ? 'active' : ''}`}
                        onClick={() => { navigate('/builder'); setIsMobileMenuOpen(false); }}
                    >
                        Builder
                    </button>
                )}
            </nav>

            {/* Right: User */}
            <div className="header-user-section" ref={dropdownRef}>
                <div
                    className="header-user-trigger"
                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                >
                    <div className="header-avatar">{initials}</div>
                    <span className="header-user">{username}</span>
                    <svg className={`dropdown-arrow ${isDropdownOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                </div>

                {isDropdownOpen && (
                    <div className="user-dropdown-menu">
                        <button className="dropdown-item" onClick={handleLogoutClick}>
                            Sign out
                        </button>
                    </div>
                )}
            </div>
        </header>
    );
}

