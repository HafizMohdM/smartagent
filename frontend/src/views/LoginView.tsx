import React, { useState, useEffect, useCallback, type FormEvent } from 'react';
import { login, register } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import LoadingDots from '../components/LoadingDots';

// ── Color tokens (same as landingPage) ───────────────────────────────────────
const C = {
  frostedWhite: '#E4DDD3',
  glacierGray: '#D1D1D1',
  steelyIce: '#929292',
  obsidian: '#222222',
  btn1: '#6F1D1B',
  btn2: '#BB9457',
  btn3: '#432818',
  btn4: '#99582A',
  btn5: '#FFE6A7',
  btn6: '#00A19B',
} as const;

// ── Inline styles ─────────────────────────────────────────────────────────────
const S = {
  page: {
    width: '100vw',
    height: '100vh',
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    fontFamily: "'DM Sans', sans-serif",
    background: C.frostedWhite,
    overflow: 'hidden',
  } as React.CSSProperties,

  left: {
    display: 'flex',
    flexDirection: 'column' as const,
    justifyContent: 'center',
    padding: '40px 56px',           // ← reduced from 60px
    background: C.frostedWhite,
    position: 'relative' as const,
    overflow: 'hidden',             // ← changed from 'auto' (fixes scrollbar bug)
    height: '100%',
  } as React.CSSProperties,

  right: {
    background: `linear-gradient(145deg, #00A19B 0%, #007a76 40%, #005f5b 100%)`,
    display: 'flex',
    flexDirection: 'column' as const,
    justifyContent: 'center',
    alignItems: 'flex-start',
    padding: '40px 48px 40px 40px',
    boxSizing: 'border-box' as const,
    position: 'relative' as const,
    overflow: 'hidden',
    height: '100%',
  } as React.CSSProperties,
} as const;

// ── Mini chart mock-up for right panel ───────────────────────────────────────
function MiniDashCard() {
  const bars = [45, 72, 58, 88, 65, 95, 70, 82, 60, 78];
  return (
    <div style={{
      background: 'rgba(250,250,250,0.06)',
      border: '1px solid rgba(187,148,87,0.25)',
      borderRadius: 16,
      padding: '20px 24px',
      width: '100%',
      maxWidth: '100%',
      backdropFilter: 'blur(12px)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#E4DDD3', letterSpacing: '0.04em' }}>Query Performance</span>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'rgba(250,250,250,0.5)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: C.btn2, display: 'inline-block' }} />
            Success
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'inline-block' }} />
            Errors
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 72 }}>
        {bars.map((h, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, height: '100%', justifyContent: 'flex-end' }}>
            <div style={{
              width: '100%',
              height: `${h}%`,
              borderRadius: '3px 3px 0 0',
              background: i === 5
                ? `linear-gradient(180deg, #E4DDD3, #00A19B)`
                : 'rgba(255,255,255,0.15)',
              transition: 'height 0.4s ease',
              position: 'relative',
            }}>
              {i === 5 && (
                <div style={{
                  position: 'absolute', bottom: 'calc(100% + 6px)', left: '50%',
                  transform: 'translateX(-50%)',
                  background: C.obsidian, color: C.btn5,
                  fontSize: 10, fontWeight: 700,
                  padding: '3px 7px', borderRadius: 4,
                  whiteSpace: 'nowrap',
                  border: `1px solid #E4DDD3`,
                }}>
                  95%
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
        {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'].map(m => (
          <span key={m} style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', flex: 1, textAlign: 'center' }}>{m}</span>
        ))}
      </div>
    </div>
  );
}

function StatPill({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div style={{
      background: 'rgba(250,250,250,0.06)',
      border: '1px solid rgba(187,148,87,0.2)',
      borderRadius: 12,
      padding: '14px 10px',
      textAlign: 'center',
      flex: 1,
      backdropFilter: 'blur(8px)',
    }}>
      <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 26, fontWeight: 900, color: C.btn5, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, fontWeight: 600, color: '#E4DDD3', marginTop: 4 }}>{label}</div>
      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function LoginView() {
  const { handleLoginSuccess } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState<'user' | 'manager'>('user');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    console.log("LoginView: Animation system initialized");
    const handleWheel = (e: WheelEvent) => {
      setScrollOffset(prev => {
        const next = prev + e.deltaY * 0.2;
        return Math.max(-150, Math.min(150, next));
      });
    };
    window.addEventListener('wheel', handleWheel, { passive: true });
    return () => window.removeEventListener('wheel', handleWheel);
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const { clientX, clientY } = e;
    const { innerWidth, innerHeight } = window;
    setMousePos({
      x: (clientX / innerWidth - 0.5) * 20,
      y: (clientY / innerHeight - 0.5) * 20
    });
  }, []);

  const navigate = useNavigate();

  const doLogin = async (emailOrUser: string, pwd: string) => {
    setError(''); setSuccess('');
    setLoading(true);
    try {
      const res = await login(emailOrUser, pwd);
      if (res?.token || res?.success || res?.access_token) {
        const finalToken = res.token || res.access_token;
        handleLoginSuccess(finalToken, res.session_id, emailOrUser, res.role);
        navigate('/dashboard');
      } else {
        setError('Invalid credentials');
      }
    } catch (err: any) {
      setError(err?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (isRegister) {
      setLoading(true);
      try {
        await register({ name: name || undefined, email, password, role });
        setSuccess('Account created! Pending admin approval.');
        setIsRegister(false);
        setEmail(''); setPassword(''); setName('');
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Registration failed');
      } finally { setLoading(false); }
      return;
    }
    await doLogin(email, password);
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px 14px',
    border: `1.5px solid ${C.glacierGray}`,
    borderRadius: 8,
    fontFamily: "'DM Sans', sans-serif",
    fontSize: '0.9rem',
    color: C.obsidian,
    background: C.frostedWhite,
    outline: 'none',
    transition: 'border-color 0.2s, box-shadow 0.2s',
    boxSizing: 'border-box',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: '0.78rem',
    fontWeight: 600,
    color: C.steelyIce,
    letterSpacing: '0.07em',
    textTransform: 'uppercase',
    marginBottom: 6,
    display: 'block',
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html, body, #root { width: 100%; height: 100%; overflow: hidden; }
 
        .auth-input:focus {
          border-color: ${C.btn6} !important;
          box-shadow: 0 0 0 3px rgba(0,161,155,0.15) !important;
        }
        .auth-input::placeholder { color: ${C.glacierGray}; }
 
        .auth-select {
          appearance: none;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23929292' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 14px center;
          padding-right: 36px !important;
          cursor: pointer;
        }
        .auth-select:focus {
          border-color: ${C.btn6} !important;
          box-shadow: 0 0 0 3px rgba(0,161,155,0.15) !important;
          outline: none;
        }
 
        .submit-btn {
          width: 100%;
          padding: 13px;
          border: none;
          border-radius: 8px;
          background: ${C.btn6};
          color: #000000;
          font-family: 'DM Sans', sans-serif;
          font-weight: 700;
          font-size: 0.95rem;
          letter-spacing: 0.04em;
          cursor: pointer;
          transition: all 0.25s ease;
          position: relative;
          overflow: hidden;
          margin-top: 4px;
        }
        .submit-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 8px 28px rgba(0,161,155,0.4);
        }
        .submit-btn:disabled { opacity: 0.65; cursor: not-allowed; }
 
        .admin-btn {
          display: flex;
          align-items: center;
          gap: 12px;
          width: 100%;
          padding: 11px 16px;
          border: 1.5px solid ${C.btn6};
          border-radius: 8px;
          background: transparent;
          cursor: pointer;
          font-family: 'DM Sans', sans-serif;
          transition: all 0.2s;
        }
        .admin-btn:hover:not(:disabled) {
          border-color: ${C.btn6};
          background: rgba(0,161,155,0.06);
          transform: translateY(-1px);
        }
 
        .toggle-btn {
          background: none;
          border: none;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.85rem;
          color: ${C.steelyIce};
          cursor: pointer;
          transition: color 0.2s;
          padding: 0;
        }
        .toggle-btn:hover { color: ${C.btn4}; }
        .toggle-btn strong { color: ${C.btn6}; font-weight: 600; }
 
        .pwd-toggle {
          position: absolute;
          right: 14px;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          cursor: pointer;
          color: ${C.steelyIce};
          padding: 0;
          display: flex;
          align-items: center;
          transition: color 0.2s;
        }
        .pwd-toggle:hover { color: ${C.btn4}; }
 
        .rp-blob {
          position: absolute;
          border-radius: 50%;
          pointer-events: none;
        }
 
        @keyframes jiggle {
          0%   { transform: rotate(0deg) scale(1); }
          15%  { transform: rotate(-8deg) scale(1.15); }
          30%  { transform: rotate(8deg) scale(1.15); }
          45%  { transform: rotate(-6deg) scale(1.1); }
          60%  { transform: rotate(6deg) scale(1.1); }
          75%  { transform: rotate(-3deg) scale(1.05); }
          90%  { transform: rotate(3deg) scale(1.05); }
          100% { transform: rotate(0deg) scale(1); }
        }
        .logo-jiggle:hover {
          animation: jiggle 0.6s ease both;
          cursor: pointer;
        }
        @keyframes float-slow {
          0%,100% { transform: translateY(0); }
          50%      { transform: translateY(-12px); }
        }
        .float-card { animation: float-slow 5s ease-in-out infinite; }
 
        .parallax-card {
          transition: transform 0.15s ease-out;
          will-change: transform;
        }
        .parallax-card:hover {
          box-shadow: 0 12px 40px rgba(0,0,0,0.25);
        }
 
        @keyframes pulse-glow {
          0%,100% { opacity: 0.08; transform: scale(1); }
          50% { opacity: 0.15; transform: scale(1.03); }
        }
        .watermark-logo {
          animation: pulse-glow 6s ease-in-out infinite;
        }
 
        @keyframes shimmerPulse {
          0%, 100% { filter: brightness(1) drop-shadow(0 8px 32px rgba(0,0,0,0.3)); transform: scale(1); }
          50% { filter: brightness(1.3) drop-shadow(0 15px 60px rgba(0,161,155,0.6)); transform: scale(1.02); }
        }
        .shimmer-logo {
          animation: shimmerPulse 2.5s ease-in-out infinite;
        }
 
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .anim-0 { animation: fadeSlideUp 0.5s 0.05s ease both; }
        .anim-1 { animation: fadeSlideUp 0.5s 0.15s ease both; }
        .anim-2 { animation: fadeSlideUp 0.5s 0.25s ease both; }
        .anim-3 { animation: fadeSlideUp 0.5s 0.35s ease both; }
        .anim-4 { animation: fadeSlideUp 0.5s 0.45s ease both; }
        .anim-5 { animation: fadeSlideUp 0.5s 0.55s ease both; }
        .anim-6 { animation: fadeSlideUp 0.5s 0.65s ease both; }
 
        @media (max-width: 860px) {
          .login-grid { grid-template-columns: 1fr !important; }
          .right-panel { display: none !important; }
          .left-panel  { padding: 40px 32px !important; }
        }
      `}</style>

      <div style={S.page} className="login-grid" onMouseMove={handleMouseMove}>

        {/* ── LEFT: Form panel ─────────────────────────────────────────── */}
        <div style={S.left} className="left-panel">
          <div style={{
            position: 'absolute', top: -80, left: -80,
            width: 260, height: 260, borderRadius: '50%',
            background: `radial-gradient(circle, rgba(153,88,42,0.06) 0%, transparent 70%)`,
            pointerEvents: 'none',
          }} />

          {/* Logo */}
          <div className="anim-0" style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 40 }}>
            <img
              src="/logo.png"
              alt="Cognivelt AI logo"
              style={{ width: 40, height: 40, objectFit: 'contain' }}
            />
            <span style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700, fontSize: 18, color: C.obsidian, letterSpacing: '-0.02em' }}>
              Cognivelt AI
            </span>
          </div>

          {/* Heading */}
          <div className="anim-1" style={{ marginBottom: 24 }}>  {/* ← reduced from 32 */}
            <h1 style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: 'clamp(26px, 3vw, 34px)',
              fontWeight: 900,
              color: C.obsidian,
              letterSpacing: '-0.03em',
              lineHeight: 1.15,
              marginBottom: 8,
            }}>
              {isRegister ? 'Request Access' : 'Welcome back'}
            </h1>
            <p style={{ fontSize: '0.9rem', color: C.steelyIce }}>
              {isRegister ? 'Fill in your details to request an account' : 'Sign in to your DataCopilot workspace'}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>  {/* ← reduced from 18 */}

            {isRegister && (
              <>
                <div className="anim-2">
                  <label style={labelStyle}>Full Name</label>
                  <input
                    className="auth-input"
                    type="text"
                    placeholder="John Doe"
                    value={name}
                    onChange={e => setName(e.target.value)}
                    style={inputStyle}
                  />
                </div>

                <div className="anim-2">
                  <label style={labelStyle}>Role</label>
                  <select
                    className="auth-input auth-select"
                    value={role}
                    onChange={e => setRole(e.target.value as 'user' | 'manager')}
                    style={{ ...inputStyle, cursor: 'pointer' }}
                  >
                    <option value="user">User — view &amp; query data</option>
                    <option value="manager">Manager — create &amp; manage connections</option>
                  </select>
                </div>
              </>
            )}

            <div className="anim-3">
              <label style={labelStyle}>Email</label>
              <input
                className="auth-input"
                id="email"
                type="text"
                placeholder={isRegister ? 'you@company.com' : 'Email or username'}
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoFocus
                style={inputStyle}
              />
            </div>

            <div className="anim-4">
              <label style={labelStyle}>Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  className="auth-input"
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  minLength={isRegister ? 6 : undefined}
                  style={{ ...inputStyle, paddingRight: 44 }}
                />
                <button type="button" className="pwd-toggle" onClick={() => setShowPwd(v => !v)}>
                  {showPwd ? (
                    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                  ) : (
                    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                  )}
                </button>
              </div>
            </div>

            {isRegister && (
              <div className="anim-4" style={{
                background: `rgba(153,88,42,0.06)`,
                border: `1px solid rgba(153,88,42,0.22)`,
                borderRadius: 8, padding: '10px 14px',
                fontSize: '0.82rem', color: C.btn4,
                display: 'flex', gap: 8, alignItems: 'flex-start',
              }}>
                <span>⏳</span>
                <span>Your account will require <strong>admin approval</strong> before you can log in.</span>
              </div>
            )}

            {error && (
              <div style={{
                background: 'rgba(111,29,27,0.07)',
                border: `1px solid rgba(111,29,27,0.25)`,
                borderRadius: 8, padding: '10px 14px',
                fontSize: '0.82rem', color: C.btn1,
                display: 'flex', gap: 8, alignItems: 'center',
              }}>
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
                {error}
              </div>
            )}

            {success && (
              <div style={{
                background: 'rgba(16,185,129,0.07)',
                border: '1px solid rgba(16,185,129,0.25)',
                borderRadius: 8, padding: '10px 14px',
                fontSize: '0.82rem', color: '#065f46',
                display: 'flex', gap: 8, alignItems: 'center',
              }}>
                <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>
                {success}
              </div>
            )}

            <button type="submit" className="submit-btn anim-5" disabled={loading}>
              {loading ? <LoadingDots /> : (isRegister ? 'Request Access' : 'Sign In')}
            </button>
          </form>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0' }}>
            <div style={{ flex: 1, height: 1, background: C.glacierGray }} />
            <span style={{ fontSize: '0.75rem', color: C.steelyIce, letterSpacing: '0.06em' }}>OR</span>
            <div style={{ flex: 1, height: 1, background: C.glacierGray }} />
          </div>

          {!isRegister && (
            <div className="anim-6" style={{ marginBottom: 20 }}>
              <p style={{ fontSize: '0.72rem', fontWeight: 700, color: C.steelyIce, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>Admin Access</p>
              <button
                className="admin-btn"
                onClick={() => doLogin('admin', 'admin123')}
                disabled={loading}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: C.btn6,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 16, flexShrink: 0,
                }}>👤</div>
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: C.obsidian }}>Login as Admin</div>
                  <div style={{ fontSize: '0.75rem', color: C.steelyIce }}>admin / admin123</div>
                </div>
              </button>
            </div>
          )}

          <button className="toggle-btn" onClick={() => { setIsRegister(!isRegister); setError(''); setSuccess(''); }}>
            {isRegister
              ? <>Already have an account? <strong>Sign In</strong></>
              : <>Don't have an account? <strong>Request Access</strong></>
            }
          </button>
        </div>

        {/* ── RIGHT: Visual panel ───────────────────────────────────────── */}
        <div style={S.right} className="right-panel">

          {/* decorative blobs */}
          <div className="rp-blob" style={{
            top: -120 + scrollOffset * 0.4 + mousePos.y * 0.5,
            right: -120 + mousePos.x * 0.3,
            width: 400, height: 400,
            background: `radial-gradient(circle, rgba(228,221,211,0.2) 0%, transparent 70%)`,
            transition: 'all 0.4s cubic-bezier(0.1, 0, 0.2, 1)'
          }} />
          <div className="rp-blob" style={{
            bottom: -80 - scrollOffset * 0.3 + mousePos.y * -0.4,
            left: -80 + mousePos.x * -0.2,
            width: 300, height: 300,
            background: `radial-gradient(circle, rgba(0,95,91,0.5) 0%, transparent 70%)`,
            transition: 'all 0.4s cubic-bezier(0.1, 0, 0.2, 1)'
          }} />

          {/* ── Watermark logo (kept) ── */}
          <img
            src="/logo2.png"
            alt=""
            style={{
              position: 'absolute',
              top: '-17%',
              left: '60%',
              transform: `translateX(-50%) translateY(${scrollOffset * 1.0 + mousePos.y * 1.5}px) rotate(${mousePos.x * 0.1}deg)`,
              width: '110%',
              maxWidth: 750,
              height: 'auto',
              opacity: 0.08,
              pointerEvents: 'none',
              zIndex: 0,
              filter: 'brightness(2) grayscale(0.4)',
              transition: 'transform 0.5s cubic-bezier(0.1, 0, 0.2, 1)'
            }}
          />

          {/* subtle grid */}
          <svg style={{ position: 'absolute', inset: 0, opacity: 0.04, pointerEvents: 'none' }} width="100%" height="100%">
            <defs>
              <pattern id="rpgrid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#rpgrid)" />
          </svg>

          {/* Content — big logo REMOVED, rest kept */}
          <div style={{ position: 'relative', zIndex: 1, width: '100%', alignSelf: 'flex-start' }}>

            <h2 style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: 'clamp(28px, 3vw, 42px)',
              fontWeight: 900,
              color: '#ffffff',
              lineHeight: 1.15,
              letterSpacing: '-0.03em',
              marginBottom: 12,
              textShadow: '0 2px 20px rgba(0,0,0,0.15)',
            }}>
              Welcome back.<br />
              <span style={{ color: '#E4DDD3' }}>Your data awaits.</span>
            </h2>

            <p style={{
              fontSize: '0.88rem', lineHeight: 1.7,
              color: 'rgba(228,221,211,0.75)',
              marginBottom: 28,
              maxWidth: '100%',
            }}>
              Query any database in plain English. AI-powered insights across all your data sources — in milliseconds.
            </p>

            {/* Floating chart card */}
            <div className="float-card" style={{ marginBottom: 16, width: '100%', borderRadius: 16 }}>
              <MiniDashCard />
            </div>

            {/* Stat pills */}
            <div style={{ display: 'flex', gap: 10, width: '100%' }}>
              <StatPill value="10k+" label="Daily Queries" sub="across all DBs" />
              <StatPill value="340ms" label="Avg Response" sub="p50 latency" />
              <StatPill value="99.9%" label="Uptime SLA" sub="guaranteed" />
            </div>

            {/* Dots indicator */}
            <div style={{ display: 'flex', gap: 6, marginTop: 20, justifyContent: 'center', position: 'relative' }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: i === 0 ? 20 : 6, height: 6,
                  borderRadius: 3,
                  background: i === 0 ? '#E4DDD3' : 'rgba(255,255,255,0.2)',
                  transition: 'all 0.3s',
                }} />
              ))}
              <div style={{
                position: 'absolute',
                bottom: -30,
                fontSize: '9px',
                color: 'rgba(255,255,255,0.15)',
                fontFamily: 'monospace'
              }}>
                ANIM_SYSTEM_V2.5_ACTIVE
              </div>

              {/* Scroll Progress Indicator */}
              <div style={{
                position: 'absolute',
                bottom: -45,
                width: 100,
                height: 2,
                background: 'rgba(255,255,255,0.1)',
                borderRadius: 1,
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${((scrollOffset + 150) / 300) * 100}%`,
                  height: '100%',
                  background: C.btn6,
                  transition: 'width 0.3s ease-out'
                }} />
              </div>
            </div>
          </div>
        </div>

      </div>
    </>
  );
}