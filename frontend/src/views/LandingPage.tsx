import { useState, useEffect, useRef } from "react";
import type { ReactNode, FC, MouseEvent } from "react";
import { useNavigate } from "react-router-dom";

// ── Color tokens ──────────────────────────────────────────────────────────────
const C = {
  frostedWhite: "#FAFAFA",
  glacierGray: "#D1D1D1",
  steelyIce: "#929292",
  obsidian: "#222222",
  btn1: "#6F1D1B",
  btn2: "#BB9457",
  btn3: "#432818",
  btn4: "#99582A",
  btn5: "#FFE6A7",
} as const;

// ── Fonts via Google Fonts (injected once) ────────────────────────────────────
const FontLink: FC = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap');
 
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body { background: ${C.frostedWhite}; color: ${C.obsidian}; font-family: 'DM Sans', sans-serif; }
 
    :root {
      --white: ${C.frostedWhite};
      --glacier: ${C.glacierGray};
      --steely: ${C.steelyIce};
      --obsidian: ${C.obsidian};
      --btn1: ${C.btn1};
      --btn2: ${C.btn2};
      --btn3: ${C.btn3};
      --btn4: ${C.btn4};
      --btn5: ${C.btn5};
    }
 
    @keyframes fadeUp {
      from { opacity:0; transform:translateY(32px); }
      to   { opacity:1; transform:translateY(0); }
    }
    @keyframes float {
      0%,100% { transform: translateY(0px); }
      50%      { transform: translateY(-14px); }
    }
    @keyframes pulse-ring {
      0%   { transform: scale(0.9); opacity:0.6; }
      100% { transform: scale(1.6); opacity:0; }
    }
    @keyframes shimmer {
      0%   { background-position: -400px 0; }
      100% { background-position: 400px 0; }
    }
    @keyframes spin-slow {
      from { transform: rotate(0deg); }
      to   { transform: rotate(360deg); }
    }
    @keyframes counter {
      from { opacity:0; transform:scale(0.7); }
      to   { opacity:1; transform:scale(1); }
    }
    @keyframes line-grow {
      from { width: 0; }
      to   { width: 100%; }
    }
    @keyframes grain {
      0%,100% { transform: translate(0,0); }
      10%     { transform: translate(-2%,-3%); }
      30%     { transform: translate(3%,2%); }
      50%     { transform: translate(-1%,4%); }
      70%     { transform: translate(4%,-1%); }
      90%     { transform: translate(-3%,3%); }
    }
 
    .fade-up { animation: fadeUp 0.7s ease both; }
    .fade-up-1 { animation: fadeUp 0.7s 0.1s ease both; }
    .fade-up-2 { animation: fadeUp 0.7s 0.2s ease both; }
    .fade-up-3 { animation: fadeUp 0.7s 0.35s ease both; }
    .fade-up-4 { animation: fadeUp 0.7s 0.5s ease both; }
 
    .btn-primary {
      background: linear-gradient(135deg, var(--btn1), var(--btn4));
      color: var(--btn5);
      border: none;
      padding: 14px 32px;
      border-radius: 4px;
      font-family: 'DM Sans', sans-serif;
      font-weight: 600;
      font-size: 15px;
      letter-spacing: 0.04em;
      cursor: pointer;
      transition: all 0.25s ease;
      position: relative;
      overflow: hidden;
    }
    .btn-primary::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,230,167,0.15), transparent);
      opacity: 0;
      transition: opacity 0.25s;
    }
    .btn-primary:hover::after { opacity: 1; }
    .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(111,29,27,0.4); }
 
    .btn-secondary {
      background: transparent;
      color: var(--btn2);
      border: 1.5px solid var(--btn2);
      padding: 13px 30px;
      border-radius: 4px;
      font-family: 'DM Sans', sans-serif;
      font-weight: 500;
      font-size: 15px;
      letter-spacing: 0.04em;
      cursor: pointer;
      transition: all 0.25s ease;
    }
    .btn-secondary:hover {
      background: var(--btn2);
      color: var(--obsidian);
      transform: translateY(-2px);
    }
 
    .btn-ghost {
      background: transparent;
      color: var(--steely);
      border: none;
      padding: 10px 20px;
      font-family: 'DM Sans', sans-serif;
      font-size: 14px;
      cursor: pointer;
      transition: color 0.2s;
    }
    .btn-ghost:hover { color: var(--obsidian); }
 
    .nav-link {
      font-family: 'DM Sans', sans-serif;
      font-size: 14px;
      font-weight: 500;
      color: var(--steely);
      text-decoration: none;
      letter-spacing: 0.02em;
      transition: color 0.2s;
      cursor: pointer;
    }
    .nav-link:hover { color: var(--obsidian); }
 
    .section-tag {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: linear-gradient(135deg, rgba(111,29,27,0.08), rgba(187,148,87,0.1));
      border: 1px solid rgba(187,148,87,0.3);
      color: var(--btn4);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      padding: 6px 14px;
      border-radius: 2px;
      margin-bottom: 20px;
    }
 
    .grain-overlay {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 9999;
      opacity: 0.025;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
      animation: grain 8s steps(2) infinite;
    }
  `}</style>
);

// ── Tiny SVG icons ────────────────────────────────────────────────────────────
const Icon = {
  db: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v6c0 1.657 4.03 3 9 3s9-1.343 9-3V5" /><path d="M3 11v6c0 1.657 4.03 3 9 3s9-1.343 9-3v-6" /></svg>,
  bolt: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>,
  shield: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>,
  chart: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" /></svg>,
  brain: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-1.14" /><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-1.14" /></svg>,
  search: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>,
  lock: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>,
  arrow: () => <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>,
  check: () => <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>,
  star: () => <svg width="14" height="14" fill={C.btn2} viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>,
  menu: () => <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></svg>,
  close: () => <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>,
  play: () => <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M5 3l14 9-14 9V3z" /></svg>,
  twitter: () => <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M22.46 6c-.77.35-1.6.58-2.46.69.88-.53 1.56-1.37 1.88-2.38-.83.5-1.75.85-2.72 1.05C18.37 4.5 17.26 4 16 4c-2.35 0-4.27 1.92-4.27 4.29 0 .34.04.67.11.98C8.28 9.09 5.11 7.38 3 4.79c-.37.63-.58 1.37-.58 2.15 0 1.49.75 2.81 1.91 3.56-.71 0-1.37-.2-1.95-.5v.03c0 2.08 1.48 3.82 3.44 4.21a4.22 4.22 0 0 1-1.93.07 4.28 4.28 0 0 0 4 2.98 8.521 8.521 0 0 1-5.33 1.84c-.34 0-.68-.02-1.02-.06C3.44 20.29 5.7 21 8.12 21 16 21 20.33 14.46 20.33 8.79c0-.19 0-.37-.01-.56.84-.6 1.56-1.36 2.14-2.23z" /></svg>,
  linkedin: () => <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" /><rect x="2" y="9" width="4" height="12" /><circle cx="4" cy="4" r="2" /></svg>,
  github: () => <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" /></svg>,
};

// ── Animated number counter ───────────────────────────────────────────────────
interface CountUpProps {
  end: number;
  suffix?: string;
  duration?: number;
}

function CountUp({ end, suffix = "", duration = 2000 }: CountUpProps) {
  const [val, setVal] = useState<number>(0);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        let start = 0;
        const step = end / (duration / 16);
        const t = setInterval(() => {
          start += step;
          if (start >= end) { setVal(end); clearInterval(t); }
          else setVal(Math.floor(start));
        }, 16);
        obs.disconnect();
      }
    }, { threshold: 0.5 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [end, duration]);

  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>;
}

// ── Header ────────────────────────────────────────────────────────────────────
const Header: FC = () => {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState<boolean>(false);
  const [open, setOpen] = useState<boolean>(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);

  const navItems: string[] = ["Features", "How It Works", "Pricing", "Docs", "Blog"];

  return (
    <header style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 1000,
      background: scrolled ? "rgba(250,250,250,0.92)" : "transparent",
      backdropFilter: scrolled ? "blur(16px)" : "none",
      borderBottom: scrolled ? `1px solid ${C.glacierGray}` : "1px solid transparent",
      transition: "all 0.3s ease",
    }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 32px", height: 68, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 6,
            background: `linear-gradient(135deg, ${C.btn1}, ${C.btn4})`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="18" height="18" fill="none" stroke={C.btn5} strokeWidth="2" viewBox="0 0 24 24">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700, fontSize: 18, color: C.obsidian, letterSpacing: "-0.02em" }}>
            cognivelt AI
          </span>
        </div>

        {/* Nav (desktop) */}
        <nav style={{ display: "flex", gap: 36, alignItems: "center" }} className="desktop-nav">
          {navItems.map(n => <a key={n} className="nav-link" href={`#${n.toLowerCase().replace(/ /g, "-")}`}>{n}</a>)}
        </nav>

        {/* CTA */}
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button className="btn-ghost" style={{ fontSize: 14 }} onClick={() => navigate("/login")}>Sign In</button>
          <button className="btn-primary" style={{ padding: "10px 22px", fontSize: 14 }}>Get Started Free</button>
          <button onClick={() => setOpen(!open)} style={{ display: "none", background: "none", border: "none", cursor: "pointer", color: C.obsidian }} className="mobile-menu-btn">
            {open ? <Icon.close /> : <Icon.menu />}
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      {open && (
        <div style={{ background: C.frostedWhite, borderTop: `1px solid ${C.glacierGray}`, padding: "20px 32px", display: "flex", flexDirection: "column", gap: 20 }}>
          {navItems.map(n => <a key={n} className="nav-link" style={{ fontSize: 16 }} href={`#${n.toLowerCase()}`} onClick={() => setOpen(false)}>{n}</a>)}
          <button className="btn-primary" style={{ width: "100%", marginTop: 8 }}>Get Started Free</button>
        </div>
      )}

      <style>{`
        @media (max-width: 768px) {
          .desktop-nav { display: none !important; }
          .mobile-menu-btn { display: block !important; }
        }
      `}</style>
    </header>
  );
};

// ── Hero ──────────────────────────────────────────────────────────────────────
const Hero: FC = () => {
  const navigate = useNavigate();
  return (
    <section style={{ minHeight: "100vh", display: "flex", alignItems: "center", position: "relative", overflow: "hidden", paddingTop: 68 }}>
      {/* Background geometric lines */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <svg width="100%" height="100%" style={{ position: "absolute", opacity: 0.06 }}>
          <defs>
            <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke={C.obsidian} strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
        {/* Warm accent blobs */}
        <div style={{ position: "absolute", top: "15%", right: "8%", width: 420, height: 420, borderRadius: "50%", background: `radial-gradient(circle, rgba(187,148,87,0.1) 0%, transparent 70%)`, filter: "blur(40px)" }} />
        <div style={{ position: "absolute", bottom: "10%", left: "5%", width: 320, height: 320, borderRadius: "50%", background: `radial-gradient(circle, rgba(111,29,27,0.08) 0%, transparent 70%)`, filter: "blur(50px)" }} />
      </div>

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "80px 32px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80, alignItems: "center", position: "relative", zIndex: 1 }}>
        {/* Left */}
        <div>
          <div className="section-tag fade-up">
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.btn4 }} />
            AI-Powered Analytics
          </div>

          <h1 className="fade-up-1" style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: "clamp(42px, 5vw, 72px)",
            fontWeight: 900,
            lineHeight: 1.06,
            letterSpacing: "-0.03em",
            color: C.obsidian,
            marginBottom: 24,
          }}>
            Ask Questions.
          </h1>

          <p className="fade-up-2" style={{ fontSize: 18, lineHeight: 1.7, color: C.steelyIce, marginBottom: 40, maxWidth: 480 }}>
            cognivelt AI is an AI analytics layer that turns plain English into SQL — across all your databases simultaneously. No more data silos. No more manual merging.
          </p>

          <div className="fade-up-3" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <button className="btn-primary" style={{ display: "flex", alignItems: "center", gap: 8 }} onClick={() => navigate("/login")}>
              Start for Free <Icon.arrow />
            </button>
            <button className="btn-secondary" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon.play /> Watch Demo
            </button>
          </div>

          <div className="fade-up-4" style={{ display: "flex", gap: 32, marginTop: 48, paddingTop: 40, borderTop: `1px solid ${C.glacierGray}` }}>
            {([["10k+", "Queries daily"], ["99.9%", "Uptime SLA"], ["<340ms", "Avg response"]] as [string, string][]).map(([n, l]) => (
              <div key={l}>
                <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 28, fontWeight: 700, color: C.obsidian }}>{n}</div>
                <div style={{ fontSize: 13, color: C.steelyIce, marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right – animated query card */}
        <div style={{ position: "relative", animation: "float 5s ease-in-out infinite" }}>
          <QueryCard />
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          section > div { grid-template-columns: 1fr !important; }
          section > div > div:last-child { display: none; }
        }
      `}</style>
    </section>
  );
};

interface QueryStep {
  q: string;
  db: string[];
  rows: number;
  ms: number;
}

const QueryCard: FC = () => {
  const [step, setStep] = useState<number>(0);
  const steps: QueryStep[] = [
    { q: "Show me revenue by department for Q4 2024", db: ["Postgres_DRT", "Postgres_TEST"], rows: 950, ms: 340 },
    { q: "Which products had >20% growth last month?", db: ["Analytics_DB"], rows: 47, ms: 210 },
    { q: "Top 10 customers by lifetime value across all regions", db: ["CRM_DB", "Sales_DB"], rows: 10, ms: 490 },
  ];
  const s = steps[step];

  useEffect(() => {
    const t = setInterval(() => setStep(p => (p + 1) % steps.length), 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{
      background: C.frostedWhite,
      border: `1px solid ${C.glacierGray}`,
      borderRadius: 16,
      padding: 28,
      boxShadow: "0 24px 80px rgba(34,34,34,0.1)",
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Top bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 20 }}>
        {(["#ff5f57", "#febc2e", "#28c840"] as string[]).map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: "50%", background: c }} />)}
        <div style={{ flex: 1, height: 24, background: C.glacierGray, borderRadius: 4, marginLeft: 8, display: "flex", alignItems: "center", paddingLeft: 10 }}>
          <span style={{ fontSize: 11, color: C.steelyIce }}>cognivelt.ai / query</span>
        </div>
      </div>

      {/* Query input */}
      <div style={{ background: `linear-gradient(135deg, rgba(111,29,27,0.04), rgba(187,148,87,0.04))`, border: `1px solid rgba(187,148,87,0.2)`, borderRadius: 8, padding: "14px 16px", marginBottom: 16, display: "flex", gap: 10, alignItems: "flex-start" }}>
        <Icon.search />
        <span style={{ fontSize: 13, color: C.obsidian, lineHeight: 1.5, flex: 1 }}>{s.q}</span>
        <div style={{ width: 2, height: 16, background: C.btn4, animation: "pulse-ring 1s ease-out infinite", borderRadius: 1 }} />
      </div>

      {/* DBs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {s.db.map(d => (
          <div key={d} style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(146,146,146,0.08)", border: `1px solid ${C.glacierGray}`, borderRadius: 4, padding: "4px 10px", fontSize: 11, color: C.steelyIce }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#28c840" }} />
            {d}
          </div>
        ))}
      </div>

      {/* SQL preview */}
      <div style={{ background: C.obsidian, borderRadius: 8, padding: 16, marginBottom: 16, fontFamily: "monospace", fontSize: 11, lineHeight: 1.7, color: C.glacierGray, overflow: "hidden" }}>
        <span style={{ color: "#BB9457" }}>SELECT </span>
        <span style={{ color: C.frostedWhite }}>department, SUM(revenue) </span>
        <span style={{ color: "#BB9457" }}>AS </span>
        <span style={{ color: "#99e0ff" }}>total</span>
        <br />
        <span style={{ color: "#BB9457" }}>FROM </span>
        <span style={{ color: "#28c840" }}>invoices</span>
        <span style={{ color: C.glacierGray }}> i </span>
        <span style={{ color: "#BB9457" }}>JOIN </span>
        <span style={{ color: "#28c840" }}>org_units</span>
        <span style={{ color: C.glacierGray }}> o</span>
        <br />
        <span style={{ color: "#BB9457" }}>  ON </span>
        <span style={{ color: C.frostedWhite }}>i.dept_id = o.id</span>
        <br />
        <span style={{ color: "#BB9457" }}>WHERE </span>
        <span style={{ color: C.frostedWhite }}>quarter = </span>
        <span style={{ color: "#FFE6A7" }}>'Q4 2024'</span>
      </div>

      {/* Result bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: C.steelyIce }}>
          <span style={{ color: C.btn4, fontWeight: 600 }}>{s.rows} rows</span> returned
        </span>
        <span style={{ fontSize: 12, color: C.steelyIce }}>
          {s.ms}ms · <span style={{ color: "#28c840" }}>●</span> live
        </span>
      </div>

      {/* Step dots */}
      <div style={{ display: "flex", justifyContent: "center", gap: 6, marginTop: 20 }}>
        {steps.map((_, i) => (
          <div key={i} onClick={() => setStep(i)} style={{ width: i === step ? 20 : 6, height: 6, borderRadius: 3, background: i === step ? C.btn4 : C.glacierGray, cursor: "pointer", transition: "all 0.3s" }} />
        ))}
      </div>
    </div>
  );
};

// ── Logos bar ─────────────────────────────────────────────────────────────────
const LogoBar: FC = () => {
  const logos: string[] = ["PostgreSQL", "MySQL", "Oracle", "MongoDB", "Snowflake", "BigQuery", "Redshift", "DynamoDB"];
  return (
    <div style={{ borderTop: `1px solid ${C.glacierGray}`, borderBottom: `1px solid ${C.glacierGray}`, padding: "28px 0", overflow: "hidden", background: "rgba(209,209,209,0.1)" }}>
      <p style={{ textAlign: "center", fontSize: 12, color: C.steelyIce, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 20 }}>
        Connects to your existing data sources
      </p>
      <div style={{ display: "flex", gap: 56, justifyContent: "center", flexWrap: "wrap", padding: "0 32px" }}>
        {logos.map(l => (
          <div key={l} style={{ fontSize: 14, fontWeight: 600, color: C.glacierGray, letterSpacing: "0.05em", transition: "color 0.2s", cursor: "default" }}
            onMouseEnter={(e: MouseEvent<HTMLDivElement>) => (e.currentTarget.style.color = C.steelyIce)}
            onMouseLeave={(e: MouseEvent<HTMLDivElement>) => (e.currentTarget.style.color = C.glacierGray)}>
            {l}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Features ──────────────────────────────────────────────────────────────────
interface FeatureItem {
  icon: ReactNode;
  title: string;
  desc: string;
  tag: string;
}

const Features: FC = () => {
  const features: FeatureItem[] = [
    { icon: <Icon.brain />, title: "AI-Driven SQL Generation", desc: "Context-aware SQL via hybrid RAG — the LLM only sees schemas relevant to your query, eliminating hallucinations on non-existent tables.", tag: "Core" },
    { icon: <Icon.db />, title: "Multi-Database Orchestration", desc: "Execute across heterogeneous databases in parallel. Results are merged in-memory with NULL-padded union-of-columns merging.", tag: "Engine" },
    { icon: <Icon.bolt />, title: "Real-Time Dashboards", desc: "Reactive widgets with 30s polling, Page Visibility API awareness, and Live Mode toggle — zero wasted cycles when you're away.", tag: "UI" },
    { icon: <Icon.shield />, title: "Production-Safe Guardrails", desc: "SELECT-only enforcement, 5MB payload rejection, per-DB 5s timeout, and global semaphore capping 5 concurrent connections.", tag: "Safety" },
    { icon: <Icon.search />, title: "Hybrid Schema Retrieval", desc: "BM25 keyword matching + pgvector semantic similarity finds the most relevant tables from thousands of schemas in milliseconds.", tag: "RAG" },
    { icon: <Icon.chart />, title: "Zero Snapshot Storage", desc: "Results are never persisted. We store SQL logic, not output rows — guaranteeing 100% freshness and complete data privacy.", tag: "Privacy" },
  ];

  return (
    <section id="features" style={{ padding: "120px 32px", maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ textAlign: "center", marginBottom: 72 }}>
        <div className="section-tag" style={{ margin: "0 auto 20px" }}>Platform Features</div>
        <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(32px,4vw,52px)", fontWeight: 900, letterSpacing: "-0.03em", color: C.obsidian, marginBottom: 20 }}>
          Everything you need to<br /><span style={{ color: C.btn4 }}>query without limits</span>
        </h2>
        <p style={{ fontSize: 17, color: C.steelyIce, maxWidth: 520, margin: "0 auto" }}>
          A complete intelligence layer between your users and your data infrastructure.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 2 }}>
        {features.map((f, i) => (
          <FeatureCard key={i} {...f} index={i} />
        ))}
      </div>
    </section>
  );
};

interface FeatureCardProps extends FeatureItem {
  index: number;
}

function FeatureCard({ icon, title, desc, tag }: FeatureCardProps) {
  const [hov, setHov] = useState<boolean>(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "40px 36px",
        border: `1px solid ${hov ? "rgba(187,148,87,0.4)" : C.glacierGray}`,
        background: hov ? "rgba(187,148,87,0.03)" : C.frostedWhite,
        transition: "all 0.3s ease",
        cursor: "default",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {hov && <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${C.btn1}, ${C.btn2})` }} />}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div style={{ width: 44, height: 44, borderRadius: 8, background: hov ? `linear-gradient(135deg, ${C.btn1}, ${C.btn4})` : "rgba(209,209,209,0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: hov ? C.btn5 : C.steelyIce, transition: "all 0.3s" }}>
          {icon}
        </div>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: C.btn4, textTransform: "uppercase", border: `1px solid rgba(187,148,87,0.3)`, padding: "3px 8px", borderRadius: 2 }}>{tag}</span>
      </div>
      <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: 20, fontWeight: 700, color: C.obsidian, marginBottom: 12, letterSpacing: "-0.01em" }}>{title}</h3>
      <p style={{ fontSize: 14, lineHeight: 1.7, color: C.steelyIce }}>{desc}</p>
    </div>
  );
}

// ── How It Works ──────────────────────────────────────────────────────────────
interface StepItem {
  n: string;
  title: string;
  desc: string;
  icon: ReactNode;
}

const HowItWorks: FC = () => {
  const steps: StepItem[] = [
    { n: "01", title: "Ask in Plain English", desc: "Type any analytics question. cognivelt AI understands context, intent, and your entire data landscape.", icon: <Icon.search /> },
    { n: "02", title: "AI Retrieves Schema", desc: "The hybrid RAG system finds the Top-5 relevant tables from thousands via semantic + keyword search.", icon: <Icon.brain /> },
    { n: "03", title: "SQL is Generated & Validated", desc: "The LLM crafts precise SQL from your question + schema context. A validation layer blocks unsafe patterns.", icon: <Icon.bolt /> },
    { n: "04", title: "Parallel Execution", desc: "Queries run across all your connected databases simultaneously with async orchestration and partial-result salvage.", icon: <Icon.db /> },
    { n: "05", title: "Results Merged & Delivered", desc: "Multi-DB rows are merged with source tagging, size-checked, and returned as charts or tables in milliseconds.", icon: <Icon.chart /> },
  ];

  return (
    <section id="how-it-works" style={{ background: C.obsidian, padding: "120px 32px", position: "relative", overflow: "hidden" }}>
      {/* decorative */}
      <div style={{ position: "absolute", top: -100, right: -100, width: 500, height: 500, borderRadius: "50%", background: `radial-gradient(circle, rgba(187,148,87,0.06) 0%, transparent 70%)`, pointerEvents: "none" }} />

      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 80 }}>
          <div className="section-tag" style={{ margin: "0 auto 20px", background: "rgba(187,148,87,0.1)", borderColor: "rgba(187,148,87,0.25)" }}>How It Works</div>
          <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(32px,4vw,52px)", fontWeight: 900, letterSpacing: "-0.03em", color: C.frostedWhite, marginBottom: 20 }}>
            From question to insight<br /><span style={{ color: C.btn2 }}>in under a second</span>
          </h2>
        </div>

        <div style={{ position: "relative" }}>
          {/* connector line */}
          <div style={{ position: "absolute", top: 36, left: "calc(10% + 18px)", right: "calc(10% + 18px)", height: 1, background: `linear-gradient(90deg, transparent, ${C.btn3}, ${C.btn2}, ${C.btn3}, transparent)`, display: "block" }} />

          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 24 }}>
            {steps.map((s, i) => (
              <StepCard key={i} {...s} />
            ))}
          </div>
        </div>
      </div>

      <style>{`@media (max-width: 900px) { #how-it-works .grid { grid-template-columns: 1fr !important; } }`}</style>
    </section>
  );
};

function StepCard({ n, title, desc, icon }: StepItem) {
  const [hov, setHov] = useState<boolean>(false);
  return (
    <div onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ textAlign: "center", padding: "0 8px", cursor: "default" }}>
      <div style={{
        width: 56, height: 56, borderRadius: "50%", margin: "0 auto 24px",
        background: hov ? `linear-gradient(135deg, ${C.btn1}, ${C.btn4})` : "rgba(255,255,255,0.05)",
        border: `1px solid ${hov ? "transparent" : "rgba(255,255,255,0.1)"}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: hov ? C.btn5 : C.steelyIce,
        transition: "all 0.3s ease",
        position: "relative", zIndex: 1,
      }}>
        {icon}
      </div>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", color: C.btn3, marginBottom: 10 }}>{n}</div>
      <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: 16, fontWeight: 700, color: C.frostedWhite, marginBottom: 10, lineHeight: 1.3 }}>{title}</h3>
      <p style={{ fontSize: 13, lineHeight: 1.7, color: C.steelyIce }}>{desc}</p>
    </div>
  );
}

// ── Stats ─────────────────────────────────────────────────────────────────────
interface StatItem {
  n: number;
  suf: string;
  label: string;
  sub: string;
}

const Stats: FC = () => {
  const stats: StatItem[] = [
    { n: 50, suf: "k+", label: "Queries executed today", sub: "across all tenants" },
    { n: 340, suf: "ms", label: "Average response time", sub: "p50 across multi-DB queries" },
    { n: 99, suf: ".9%", label: "Platform uptime SLA", sub: "backed by our guarantee" },
    { n: 5, suf: "MB", label: "Max payload guard", sub: "hard limit per response" },
  ];
  return (
    <section style={{ padding: "100px 32px", background: `linear-gradient(135deg, rgba(111,29,27,0.04), rgba(187,148,87,0.06))`, borderTop: `1px solid ${C.glacierGray}`, borderBottom: `1px solid ${C.glacierGray}` }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 48, textAlign: "center" }}>
        {stats.map((s, i) => (
          <div key={i}>
            <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 56, fontWeight: 900, color: C.obsidian, letterSpacing: "-0.04em", lineHeight: 1 }}>
              <CountUp end={s.n} suffix={s.suf} />
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.obsidian, marginTop: 12, marginBottom: 4 }}>{s.label}</div>
            <div style={{ fontSize: 12, color: C.steelyIce }}>{s.sub}</div>
          </div>
        ))}
      </div>
    </section>
  );
};

// ── Testimonials ──────────────────────────────────────────────────────────────
interface TestimonialItem {
  name: string;
  role: string;
  quote: string;
  avatar: string;
}

const Testimonials: FC = () => {
  const testimonials: TestimonialItem[] = [
    { name: "Sarah Chen", role: "Head of Data, Fintech Co.", quote: "We went from 3-day BI turnarounds to answers in seconds. cognivelt AI queries our 6 Postgres instances like they're one.", avatar: "SC" },
    { name: "Raj Mehta", role: "CTO, E-commerce Platform", quote: "The RAG-based schema retrieval is witchcraft. It picks the right tables from 400+ every single time. Our analysts are dangerous now.", avatar: "RM" },
    { name: "Anna Kowalski", role: "Senior Data Engineer", quote: "The execution engine handles partial salvage beautifully. Slow DBs don't block the fast ones. It's production-grade architecture.", avatar: "AK" },
    { name: "Marcus Osei", role: "VP Analytics, SaaS Co.", quote: "We embedded cognivelt AI into our customer portal. Non-technical users are building their own dashboards in minutes.", avatar: "MO" },
  ];

  return (
    <section id="testimonials" style={{ padding: "120px 32px", maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ textAlign: "center", marginBottom: 72 }}>
        <div className="section-tag" style={{ margin: "0 auto 20px" }}>What People Say</div>
        <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(32px,4vw,52px)", fontWeight: 900, letterSpacing: "-0.03em", color: C.obsidian }}>
          Trusted by data teams<br /><span style={{ color: C.btn4 }}>who ship fast</span>
        </h2>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 24 }}>
        {testimonials.map((t, i) => <TestimonialCard key={i} {...t} />)}
      </div>
    </section>
  );
};

function TestimonialCard({ name, role, quote, avatar }: TestimonialItem) {
  const [hov, setHov] = useState<boolean>(false);
  return (
    <div onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ padding: 32, border: `1px solid ${hov ? "rgba(187,148,87,0.4)" : C.glacierGray}`, borderRadius: 12, background: hov ? "rgba(187,148,87,0.02)" : C.frostedWhite, transition: "all 0.3s", position: "relative" }}>
      <div style={{ display: "flex", gap: 2, marginBottom: 20 }}>
        {[...Array(5)].map((_, i) => <Icon.star key={i} />)}
      </div>
      <p style={{ fontSize: 15, lineHeight: 1.7, color: C.obsidian, marginBottom: 28, fontStyle: "italic" }}>"{quote}"</p>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 40, height: 40, borderRadius: "50%", background: `linear-gradient(135deg, ${C.btn1}, ${C.btn4})`, display: "flex", alignItems: "center", justifyContent: "center", color: C.btn5, fontSize: 13, fontWeight: 700 }}>
          {avatar}
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.obsidian }}>{name}</div>
          <div style={{ fontSize: 12, color: C.steelyIce }}>{role}</div>
        </div>
      </div>
    </div>
  );
}

// ── Pricing ───────────────────────────────────────────────────────────────────
interface PricePlan {
  name: string;
  price: number | string;
  desc: string;
  popular: boolean;
  features: string[];
  cta: string;
  btnClass: string;
}
const Pricing: FC = () => {
  const [annual, setAnnual] = useState<boolean>(false);
  const plans: PricePlan[] = [
    {
      name: "Starter", price: annual ? 29 : 39, desc: "Perfect for small teams exploring AI analytics.", popular: false,
      features: ["3 database connections", "10k queries / month", "5 dashboard reports", "BM25 schema retrieval", "Community support"],
      cta: "Start Free Trial", btnClass: "btn-secondary"
    },
    {
      name: "Pro", price: annual ? 99 : 129, desc: "For growing data teams that need power and reliability.", popular: true,
      features: ["Unlimited DB connections", "100k queries / month", "Unlimited dashboards", "Hybrid RAG retrieval", "Real-time collaboration", "Priority support", "Audit logs & RBAC"],
      cta: "Get Started", btnClass: "btn-primary"
    },
    {
      name: "Enterprise", price: "Custom", desc: "For organisations with compliance, scale, and custom needs.", popular: false,
      features: ["Everything in Pro", "SSO / SAML", "Custom data connectors", "Dedicated infra", "SLA guarantee", "White-glove onboarding", "Custom contracts"],
      cta: "Talk to Sales", btnClass: "btn-secondary"
    },
  ];

  return (
    <section id="pricing" style={{ padding: "120px 32px", background: C.obsidian }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 64 }}>
          <div className="section-tag" style={{ margin: "0 auto 20px", background: "rgba(187,148,87,0.1)", borderColor: "rgba(187,148,87,0.25)" }}>Pricing</div>
          <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(32px,4vw,52px)", fontWeight: 900, letterSpacing: "-0.03em", color: C.frostedWhite, marginBottom: 20 }}>
            Simple, transparent pricing
          </h2>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 12, background: "rgba(255,255,255,0.05)", padding: "8px 20px", borderRadius: 40, border: `1px solid rgba(255,255,255,0.08)` }}>
            <span style={{ fontSize: 14, color: annual ? C.steelyIce : C.frostedWhite }}>Monthly</span>
            <div onClick={() => setAnnual(!annual)} style={{ width: 40, height: 22, borderRadius: 11, background: annual ? C.btn4 : "rgba(255,255,255,0.15)", position: "relative", cursor: "pointer", transition: "background 0.3s" }}>
              <div style={{ width: 16, height: 16, borderRadius: "50%", background: "white", position: "absolute", top: 3, left: annual ? 21 : 3, transition: "left 0.3s" }} />
            </div>
            <span style={{ fontSize: 14, color: annual ? C.frostedWhite : C.steelyIce }}>Annual <span style={{ color: C.btn2, fontSize: 11, fontWeight: 600 }}>–25%</span></span>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 24, alignItems: "start" }}>
          {plans.map((p, i) => <PriceCard key={i} {...p} />)}
        </div>
      </div>

      <style>{`@media (max-width: 900px) { #pricing .grid { grid-template-columns: 1fr !important; } }`}</style>
    </section>
  );
};

function PriceCard({ name, price, desc, popular, features, cta, btnClass }: PricePlan) {
  return (
    <div style={{
      padding: 36, borderRadius: 12,
      border: `1px solid ${popular ? C.btn2 : "rgba(255,255,255,0.1)"}`,
      background: popular ? `linear-gradient(160deg, rgba(111,29,27,0.15), rgba(187,148,87,0.08))` : "rgba(255,255,255,0.03)",
      position: "relative",
    }}>
      {popular && (
        <div style={{ position: "absolute", top: -1, left: "50%", transform: "translateX(-50%)", background: `linear-gradient(90deg, ${C.btn1}, ${C.btn4})`, color: C.btn5, fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", padding: "4px 16px", borderRadius: "0 0 6px 6px" }}>
          MOST POPULAR
        </div>
      )}
      <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.06em", color: C.btn2, textTransform: "uppercase", marginBottom: 12 }}>{name}</div>
      <div style={{ marginBottom: 8 }}>
        {typeof price === "number" ? (
          <><span style={{ fontFamily: "'Playfair Display', serif", fontSize: 48, fontWeight: 900, color: C.frostedWhite }}>${price}</span><span style={{ fontSize: 14, color: C.steelyIce }}>/mo</span></>
        ) : (
          <span style={{ fontFamily: "'Playfair Display', serif", fontSize: 40, fontWeight: 900, color: C.frostedWhite }}>{price}</span>
        )}
      </div>
      <p style={{ fontSize: 13, color: C.steelyIce, marginBottom: 28, lineHeight: 1.6 }}>{desc}</p>
      <button className={btnClass} style={{ width: "100%", marginBottom: 28 }}>{cta}</button>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {features.map(f => (
          <div key={f} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ marginTop: 1, color: C.btn2, flexShrink: 0 }}><Icon.check /></div>
            <span style={{ fontSize: 13, color: C.steelyIce, lineHeight: 1.5 }}>{f}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── CTA Banner ────────────────────────────────────────────────────────────────
const CTABanner: FC = () => {
  const navigate = useNavigate();
  return (
    <section style={{ padding: "100px 32px", position: "relative", overflow: "hidden", background: `linear-gradient(135deg, ${C.btn1}, ${C.btn3})` }}>
      <div style={{ position: "absolute", inset: 0, opacity: 0.06 }}>
        <svg width="100%" height="100%"><defs><pattern id="ctag" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" /></pattern></defs><rect width="100%" height="100%" fill="url(#ctag)" /></svg>
      </div>
      <div style={{ maxWidth: 700, margin: "0 auto", textAlign: "center", position: "relative", zIndex: 1 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(255,230,167,0.15)", border: "1px solid rgba(255,230,167,0.3)", color: C.btn5, fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", padding: "6px 14px", borderRadius: 2, marginBottom: 24 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.btn5 }} />
          Start Today — Free
        </div>
        <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: "clamp(32px,5vw,60px)", fontWeight: 900, color: C.frostedWhite, lineHeight: 1.1, letterSpacing: "-0.03em", marginBottom: 20 }}>
          Stop writing SQL.<br />Start getting answers.
        </h2>
        <p style={{ fontSize: 17, color: "rgba(250,250,250,0.75)", marginBottom: 40, lineHeight: 1.7 }}>
          Connect your first database in 60 seconds. No credit card required.
        </p>
        <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
          <button
            style={{ background: C.btn5, color: C.btn3, border: "none", padding: "16px 36px", borderRadius: 4, fontFamily: "'DM Sans',sans-serif", fontWeight: 700, fontSize: 15, cursor: "pointer", transition: "all 0.25s", letterSpacing: "0.02em" }}
            onClick={() => navigate("/login")}
            onMouseEnter={(e: MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 28px rgba(0,0,0,0.3)"; }}
            onMouseLeave={(e: MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "none"; }}>
            Get Started Free →
          </button>
          <button
            style={{ background: "transparent", color: C.btn5, border: "1.5px solid rgba(255,230,167,0.5)", padding: "14px 32px", borderRadius: 4, fontFamily: "'DM Sans',sans-serif", fontWeight: 500, fontSize: 15, cursor: "pointer", transition: "all 0.25s" }}
            onMouseEnter={(e: MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.borderColor = C.btn5; e.currentTarget.style.transform = "translateY(-2px)"; }}
            onMouseLeave={(e: MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.borderColor = "rgba(255,230,167,0.5)"; e.currentTarget.style.transform = "translateY(0)"; }}>
            Schedule a Demo
          </button>
        </div>
      </div>
    </section>
  );
};

// ── Footer ────────────────────────────────────────────────────────────────────
interface FooterColumn {
  title: string;
  links: string[];
}

const Footer: FC = () => {
  const cols: FooterColumn[] = [
    { title: "Product", links: ["Features", "How It Works", "Pricing", "Changelog", "Roadmap"] },
    { title: "Developers", links: ["Documentation", "API Reference", "SDK", "Open Source", "Status Page"] },
    { title: "Company", links: ["About", "Blog", "Careers", "Press Kit", "Contact"] },
    { title: "Legal", links: ["Privacy Policy", "Terms of Service", "Cookie Policy", "Security"] },
  ];

  const socialIcons: FC[] = [Icon.twitter, Icon.linkedin, Icon.github];

  return (
    <footer style={{ background: "#181818", borderTop: "1px solid rgba(255,255,255,0.06)", padding: "80px 32px 40px" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr", gap: 48, marginBottom: 64 }}>
          {/* Brand */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <div style={{ width: 34, height: 34, borderRadius: 6, background: `linear-gradient(135deg, ${C.btn1}, ${C.btn4})`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="18" height="18" fill="none" stroke={C.btn5} strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <span style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700, fontSize: 18, color: C.frostedWhite }}>cognivelt AI</span>
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: C.steelyIce, maxWidth: 260, marginBottom: 24 }}>
              The AI analytics layer that makes every database feel like one.
            </p>
            <div style={{ display: "flex", gap: 12 }}>
              {socialIcons.map((I, i) => (
                <div key={i}
                  style={{ width: 36, height: 36, borderRadius: 6, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", display: "flex", alignItems: "center", justifyContent: "center", color: C.steelyIce, cursor: "pointer", transition: "all 0.2s" }}
                  onMouseEnter={(e: MouseEvent<HTMLDivElement>) => { e.currentTarget.style.background = "rgba(187,148,87,0.15)"; e.currentTarget.style.color = C.btn2; }}
                  onMouseLeave={(e: MouseEvent<HTMLDivElement>) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = C.steelyIce; }}>
                  <I />
                </div>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {cols.map(col => (
            <div key={col.title}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", color: C.steelyIce, textTransform: "uppercase", marginBottom: 20 }}>{col.title}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {col.links.map(l => (
                  <a key={l} href="#"
                    style={{ fontSize: 14, color: "rgba(146,146,146,0.8)", textDecoration: "none", transition: "color 0.2s" }}
                    onMouseEnter={(e: MouseEvent<HTMLAnchorElement>) => (e.currentTarget.style.color = C.frostedWhite)}
                    onMouseLeave={(e: MouseEvent<HTMLAnchorElement>) => (e.currentTarget.style.color = "rgba(146,146,146,0.8)")}>
                    {l}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 32, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
          <span style={{ fontSize: 13, color: C.steelyIce }}>© 2026 cognivelt AI. All rights reserved by Esquare Software India</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#28c840" }} />
            <span style={{ fontSize: 13, color: C.steelyIce }}>All systems operational</span>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          footer > div > div:first-child { grid-template-columns: 1fr 1fr !important; }
        }
        @media (max-width: 480px) {
          footer > div > div:first-child { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </footer>
  );
};

// ── LandingPage Component ─────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column" }}>
      <FontLink />
      <div className="grain-overlay" />
      <Header />
      <main>
        <Hero />
        <LogoBar />
        <Features />
        <HowItWorks />
        <Stats />
        <Testimonials />
        <Pricing />
        <CTABanner />
      </main>
      <Footer />
    </div>
  );
}