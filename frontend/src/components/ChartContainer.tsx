import React from 'react';
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  PieChart, Pie,
  AreaChart, Area,
  ScatterChart, Scatter,
  XAxis, YAxis, ZAxis,
  CartesianGrid, Tooltip, Legend, Cell,
} from 'recharts';
import type { ChartConfig } from '../api/client';

interface Props { config: ChartConfig; }

// ── Palette ───────────────────────────────────────────────────────────────────
const P = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6'];
const PAGE = 100;

function toNum(v: any): number {
  if (typeof v === 'number') return v;
  const n = parseFloat(String(v));
  return isNaN(n) ? 0 : n;
}

function norm(data: any[], x?: string, y?: string) {
  return data.map(r => ({ ...r, name: String(r[x ?? ''] ?? '—'), value: toNum(r[y ?? '']) }));
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1e293b', border: 'none', borderRadius: 8, padding: '8px 12px',
      color: '#f8fafc', fontSize: '0.78rem', boxShadow: '0 4px 20px rgba(0,0,0,0.25)'
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4, color: '#94a3b8' }}>{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color || '#fff' }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</strong>
        </div>
      ))}
    </div>
  );
};

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ config }: { config: ChartConfig }) {
  const val = config.kpi_value ?? (config.data[0] ? toNum(config.data[0][config.y_axis ?? '']) : 0);
  return (
    <div className="kpi-card">
      <div className="kpi-value">{typeof val === 'number' ? val.toLocaleString() : val}</div>
      <div className="kpi-label">{config.y_axis?.replace(/_/g, ' ') ?? 'Value'}</div>
    </div>
  );
}

// ── Gauge ─────────────────────────────────────────────────────────────────────
function GaugeChart({ config }: { config: ChartConfig }) {
  const val = config.data[0] ? toNum(config.data[0][config.y_axis ?? '']) : 0;
  const pct = Math.min(100, Math.max(0, val));
  const angle = (pct / 100) * 180;
  const r = 70, cx = 100, cy = 90;
  const toXY = (deg: number) => ({
    x: cx + r * Math.cos((Math.PI * (180 + deg)) / 180),
    y: cy + r * Math.sin((Math.PI * (180 + deg)) / 180),
  });
  const start = toXY(0), end = toXY(angle);
  const large = angle > 180 ? 1 : 0;
  const arcPath = `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`;
  const bgPath = `M ${toXY(0).x} ${toXY(0).y} A ${r} ${r} 0 1 1 ${toXY(180).x} ${toXY(180).y}`;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
      <svg viewBox="0 0 200 110" width={200} height={110}>
        <path d={bgPath} fill="none" stroke="#e2e8f0" strokeWidth={14} strokeLinecap="round" />
        <path d={arcPath} fill="none" stroke="url(#gaugeGrad)" strokeWidth={14} strokeLinecap="round" />
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
        </defs>
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize={22} fontWeight={800} fill="#1e293b">
          {val.toLocaleString()}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fontSize={10} fill="#94a3b8">
          {config.y_axis?.replace(/_/g, ' ')}
        </text>
        <circle cx={cx} cy={cy} r={4} fill="#6366f1" />
      </svg>
    </div>
  );
}

// ── Heatmap ───────────────────────────────────────────────────────────────────
function HeatmapChart({ config }: { config: ChartConfig }) {
  const { x_axis, y_axis, value_col, data } = config;
  if (!x_axis || !y_axis || !value_col) return <div className="chart-placeholder">Heatmap needs x, y, value columns</div>;
  const xs = [...new Set(data.map(r => String(r[x_axis])))];
  const ys = [...new Set(data.map(r => String(r[y_axis])))];
  const map: Record<string, number> = {};
  data.forEach(r => { map[`${r[x_axis]}|${r[y_axis]}`] = toNum(r[value_col]); });
  const max = Math.max(...Object.values(map), 1);
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="heatmap-table">
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '4px 8px' }}>{y_axis} ╲ {x_axis}</th>
            {xs.map(x => <th key={x}>{x}</th>)}
          </tr>
        </thead>
        <tbody>
          {ys.map(y => (
            <tr key={y}>
              <td style={{ fontWeight: 600, color: 'var(--text-secondary)', textAlign: 'left', padding: '4px 8px' }}>{y}</td>
              {xs.map(x => {
                const v = map[`${x}|${y}`] ?? 0;
                const t = v / max;
                const bg = `rgba(99,102,241,${0.08 + t * 0.82})`;
                return (
                  <td key={x} title={`${x}, ${y}: ${v}`}
                    style={{ background: bg, color: t > 0.55 ? '#fff' : 'var(--text-primary)' }}>
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Histogram ─────────────────────────────────────────────────────────────────
function HistogramChart({ config }: { config: ChartConfig }) {
  const { x_axis, data } = config;
  if (!x_axis) return <div className="chart-placeholder">Histogram needs x_axis</div>;
  const vals = data.map(r => toNum(r[x_axis])).filter(v => !isNaN(v));
  if (!vals.length) return <div className="chart-placeholder">No numeric data</div>;
  const min = Math.min(...vals), max = Math.max(...vals);
  const bins = 10, w = (max - min) / bins || 1;
  const counts = Array(bins).fill(0);
  vals.forEach(v => { counts[Math.min(bins - 1, Math.floor((v - min) / w))]++; });
  const hd = counts.map((c, i) => ({ name: `${(min + i * w).toFixed(1)}`, count: c }));
  return (
    <BarChart data={hd} barCategoryGap="2%">
      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
      <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
      <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
      <Tooltip content={<CustomTooltip />} />
      <Bar dataKey="count" fill="#6366f1" name="Frequency" radius={[3, 3, 0, 0]} />
    </BarChart>
  );
}

// ── Treemap ───────────────────────────────────────────────────────────────────
function TreemapChart({ config }: { config: ChartConfig }) {
  const { x_axis, y_axis, data } = config;
  if (!x_axis || !y_axis) return <div className="chart-placeholder">Treemap needs x and y</div>;
  const total = data.reduce((s, r) => s + toNum(r[y_axis]), 0) || 1;
  return (
    <div className="treemap-container">
      {data.slice(0, 30).map((row, i) => {
        const pct = (toNum(row[y_axis]) / total) * 100;
        return (
          <div key={i} className="treemap-cell" title={`${row[x_axis]}: ${row[y_axis]}`}
            style={{ width: `${Math.max(pct, 4)}%`, background: P[i % P.length] }}>
            {String(row[x_axis])}
          </div>
        );
      })}
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
function TableView({ data, page, setPage }: { data: any[]; page: number; setPage: (p: number) => void }) {
  const total = Math.ceil(data.length / PAGE);
  const rows = data.slice(page * PAGE, (page + 1) * PAGE);
  return (
    <div className="table-preview-container">
      <table className="preview-table">
        <thead>
          <tr>{Object.keys(data[0] || {}).map(k => <th key={k}>{k}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>{Object.values(row).map((v: any, j) => <td key={j}>{String(v ?? '')}</td>)}</tr>
          ))}
        </tbody>
      </table>
      {total > 1 && (
        <div className="table-pagination">
          <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>‹ Prev</button>
          <span>Page {page + 1} of {total} &nbsp;·&nbsp; {data.length} rows</span>
          <button onClick={() => setPage(Math.min(total - 1, page + 1))} disabled={page === total - 1}>Next ›</button>
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
const ChartContainer: React.FC<Props> = ({ config }) => {
  const { type, chart_type, x_axis, y_axis, stack_col, data } = config;
  const resolved = chart_type || type;
  const isTable = resolved === 'table';
  const isKpi = resolved === 'kpi_card' || resolved === 'gauge';

  const [view, setView] = React.useState<'chart' | 'table'>(isTable ? 'table' : 'chart');
  const [page, setPage] = React.useState(0);
  React.useEffect(() => { setPage(0); }, [data]);

  if (!data || data.length === 0) {
    return <div className="chart-placeholder">📊 No data available</div>;
  }

  // Non-Recharts charts
  const custom: Record<string, React.ReactNode> = {
    kpi_card: <KpiCard config={config} />,
    gauge: <GaugeChart config={config} />,
    heatmap: <HeatmapChart config={config} />,
    histogram: <HistogramChart config={config} />,
    treemap: <TreemapChart config={config} />,
  };

  const renderRechart = () => {
    const cd = norm(data, x_axis, y_axis);
    const axisStyle = { tick: { fontSize: 11, fill: '#94a3b8' }, axisLine: false, tickLine: false };

    switch (resolved) {
      case 'line':
        return (
          <LineChart data={cd}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="name" {...axisStyle} />
            <YAxis {...axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
            <Line type="monotone" dataKey="value" stroke={P[0]} strokeWidth={2.5}
              name={y_axis || 'Value'} dot={{ r: 3, fill: P[0] }} activeDot={{ r: 6 }} />
          </LineChart>
        );

      case 'area':
        return (
          <AreaChart data={cd}>
            <defs>
              <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={P[0]} stopOpacity={0.25} />
                <stop offset="95%" stopColor={P[0]} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="name" {...axisStyle} />
            <YAxis {...axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
            <Area type="monotone" dataKey="value" stroke={P[0]} fill="url(#ag)"
              strokeWidth={2.5} name={y_axis || 'Value'} />
          </AreaChart>
        );

      case 'horizontal_bar':
        return (
          <BarChart data={cd} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(0,0,0,0.06)" />
            <XAxis type="number" {...axisStyle} />
            <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" radius={[0, 5, 5, 0]} name={y_axis || 'Value'}>
              {cd.map((_, i) => <Cell key={i} fill={P[i % P.length]} />)}
            </Bar>
          </BarChart>
        );

      case 'stacked_bar': {
        const keys = stack_col ? [...new Set(data.map(r => String(r[stack_col])))] : [];
        const pivoted: Record<string, any> = {};
        data.forEach(r => {
          const xv = String(r[x_axis ?? ''] ?? '—');
          if (!pivoted[xv]) pivoted[xv] = { name: xv };
          const k = stack_col ? String(r[stack_col]) : 'value';
          pivoted[xv][k] = (pivoted[xv][k] ?? 0) + toNum(r[y_axis ?? '']);
        });
        const sd = Object.values(pivoted);
        return (
          <BarChart data={sd}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="name" {...axisStyle} />
            <YAxis {...axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
            {(keys.length ? keys : ['value']).map((k, i) => (
              <Bar key={k} dataKey={k} stackId="s" fill={P[i % P.length]} radius={i === keys.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]} />
            ))}
          </BarChart>
        );
      }

      case 'combo':
        return (
          <BarChart data={cd}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="name" {...axisStyle} />
            <YAxis yAxisId="l" {...axisStyle} />
            <YAxis yAxisId="r" orientation="right" {...axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
            <Bar yAxisId="l" dataKey="value" fill={P[2]} name={y_axis || 'Value'} radius={[4, 4, 0, 0]} opacity={0.85} />
            <Line yAxisId="r" type="monotone" dataKey="value" stroke={P[0]} strokeWidth={2.5} dot={false} name="Trend" />
          </BarChart>
        );

      case 'pie':
        return (
          <PieChart>
            <Pie data={cd} cx="50%" cy="50%" outerRadius={90} innerRadius={30}
              dataKey="value" nameKey="name" paddingAngle={2}
              label={({ name, percent }: any) => `${name} (${(percent * 100).toFixed(0)}%)`}
              labelLine={{ stroke: '#94a3b8', strokeWidth: 1 }}>
              {cd.map((_, i) => <Cell key={i} fill={P[i % P.length]} />)}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
          </PieChart>
        );

      case 'scatter':
        return (
          <ScatterChart>
            <CartesianGrid stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey={x_axis} name={x_axis} type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <YAxis dataKey={y_axis} name={y_axis} type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <ZAxis range={[50, 50]} />
            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
            <Scatter data={data} fill={P[0]} opacity={0.75} />
          </ScatterChart>
        );

      case 'bar':
      default:
        return (
          <BarChart data={cd}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="name" {...axisStyle} />
            <YAxis {...axisStyle} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.78rem' }} />
            <Bar dataKey="value" name={y_axis || 'Value'} radius={[5, 5, 0, 0]}>
              {cd.map((_, i) => <Cell key={i} fill={P[i % P.length]} />)}
            </Bar>
          </BarChart>
        );
    }
  };

  return (
    <div className="chart-wrapper">
      {!isKpi && (
        <div className="chart-toggle-header">
          <div className="chart-toggle-group">
            <button className={`chart-toggle-btn ${view === 'table' ? 'active' : ''}`}
              onClick={() => setView('table')}>📄 Table</button>
            <button className={`chart-toggle-btn ${view === 'chart' ? 'active' : ''}`}
              onClick={() => setView('chart')}>📊 Chart</button>
          </div>
        </div>
      )}

      <div style={{ flex: 1, minHeight: isKpi ? 140 : 220 }}>
        {isKpi ? (
          custom[resolved]
        ) : view === 'table' ? (
          <TableView data={data} page={page} setPage={setPage} />
        ) : custom[resolved] ? (
          <div style={{ height: 240, overflow: 'auto' }}>{custom[resolved]}</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            {renderRechart() as React.ReactElement}
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default ChartContainer;
