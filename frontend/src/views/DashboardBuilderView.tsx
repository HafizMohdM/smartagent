import { useState, useEffect, useCallback, useRef } from 'react';
// react-grid-layout v2 — import the default export and cast to avoid readonly type conflicts
import _GridLayout from 'react-grid-layout';
const GridLayout = _GridLayout as any;
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import {
  getDashboards, createDashboard, getDashboard, updateDashboard, deleteDashboard,
  addWidget, deleteWidget, saveLayout, getWidgetData,
  getSavedQueries, getConnections, getSavedQueryPreview,
  type DashboardItem, type DashboardDetail, type WidgetItem, type SavedQueryItem,
  type ReportDataResponse, type DBConnectionItem,
} from '../api/client';
import ChartContainer from '../components/ChartContainer';
import LoadingDots from '../components/LoadingDots';

// ── Chart catalogue (same as ReportBuilder) ───────────────────────
const CHART_TYPES = [
  { type: 'bar', label: 'Bar', icon: '📊' },
  { type: 'line', label: 'Line', icon: '📈' },
  { type: 'area', label: 'Area', icon: '🏔️' },
  { type: 'pie', label: 'Pie', icon: '🥧' },
  { type: 'horizontal_bar', label: 'H-Bar', icon: '↔️' },
  { type: 'stacked_bar', label: 'Stacked', icon: '🗂️' },
  { type: 'scatter', label: 'Scatter', icon: '✦' },
  { type: 'heatmap', label: 'Heatmap', icon: '🌡️' },
  { type: 'histogram', label: 'Histogram', icon: '📉' },
  { type: 'treemap', label: 'Treemap', icon: '🗺️' },
  { type: 'kpi_card', label: 'KPI', icon: '🎯' },
  { type: 'gauge', label: 'Gauge', icon: '⏱️' },
  { type: 'table', label: 'Table', icon: '📄' },
];

const AXES_NEEDED: Record<string, string[]> = {
  kpi_card: ['y'], gauge: ['y'], histogram: ['x'], table: [],
  heatmap: ['x', 'y', 'value_col'], scatter: ['x', 'y'],
};
function axesFor(t: string) { return AXES_NEEDED[t] ?? ['x', 'y']; }

// ── Widget data cache ─────────────────────────────────────────────
type WidgetData = { loading: boolean; error: string | null; result: ReportDataResponse | null };

// ── Add-widget modal ──────────────────────────────────────────────
interface AddWidgetModalProps {
  dashboardId: string;
  queries: SavedQueryItem[];
  onAdd: (w: WidgetItem) => void;
  onClose: () => void;
}

function AddWidgetModal({ dashboardId, queries, onAdd, onClose }: AddWidgetModalProps) {
  const [queryId, setQueryId]     = useState('');
  const [title, setTitle]         = useState('New Widget');
  const [chartType, setChartType] = useState('bar');
  const [xAxis, setXAxis]         = useState('');
  const [yAxis, setYAxis]         = useState('');
  const [valCol, setValCol]       = useState('');
  const [cols, setCols]           = useState<string[]>([]);
  const [saving, setSaving]       = useState(false);
  const [err, setErr]             = useState('');

  // Load columns from live preview when query changes
  useEffect(() => {
    if (!queryId) { setCols([]); return; }
    
    const fetchSchema = async () => {
      try {
        const preview = await getSavedQueryPreview(queryId);
        if (preview.results && preview.results.length > 0) {
          setCols(Object.keys(preview.results[0]));
        } else {
          setCols([]);
        }
      } catch (e) {
        console.error("Failed to fetch query schema:", e);
        setCols([]);
      }
    };

    fetchSchema();
    setXAxis(''); setYAxis(''); setValCol('');
  }, [queryId]);

  const axes = axesFor(chartType);

  const handleAdd = async () => {
    if (!queryId) { setErr('Select a query'); return; }
    setSaving(true); setErr('');
    try {
      const w = await addWidget({
        dashboard_id: dashboardId,
        query_id: queryId,
        title, chart_type: chartType,
        config: { x_axis: xAxis || undefined, y_axis: yAxis || undefined, value_col: valCol || undefined },
        grid_x: 0, grid_y: 9999, grid_w: 6, grid_h: 4,
      });
      onAdd(w);
    } catch (e: any) { setErr(e.message || 'Failed'); }
    finally { setSaving(false); }
  };

  return (
    <div className="db-modal-overlay" onClick={onClose}>
      <div className="db-modal" onClick={e => e.stopPropagation()}>
        <div className="db-modal-header">
          <h3>Add Widget</h3>
          <button className="db-modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="db-modal-body">
          <div className="field-group">
            <label>Widget Title</label>
            <input value={title} onChange={e => setTitle(e.target.value)} />
          </div>

          <div className="field-group">
            <label>Source Query</label>
            <select value={queryId} onChange={e => setQueryId(e.target.value)}>
              <option value="">Select query…</option>
              {queries.map(q => <option key={q.id} value={q.id}>{q.title}</option>)}
            </select>
          </div>

          <div className="field-group">
            <label>Chart Type</label>
            <div className="db-chart-picker">
              {CHART_TYPES.map(c => (
                <button key={c.type}
                        className={`db-chart-btn ${chartType === c.type ? 'active' : ''}`}
                        onClick={() => setChartType(c.type)}>
                  {c.icon} {c.label}
                </button>
              ))}
            </div>
          </div>

          {cols.length > 0 && axes.length > 0 && (
            <div className="field-row">
              {axes.includes('x') && (
                <div className="field-group">
                  <label>X-Axis</label>
                  <select value={xAxis} onChange={e => setXAxis(e.target.value)}>
                    <option value="">Select…</option>
                    {cols.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}
              {axes.includes('y') && (
                <div className="field-group">
                  <label>{chartType === 'kpi_card' || chartType === 'gauge' ? 'Value' : 'Y-Axis'}</label>
                  <select value={yAxis} onChange={e => setYAxis(e.target.value)}>
                    <option value="">Select…</option>
                    {cols.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}
              {axes.includes('value_col') && (
                <div className="field-group">
                  <label>Value Col</label>
                  <select value={valCol} onChange={e => setValCol(e.target.value)}>
                    <option value="">Select…</option>
                    {cols.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}
            </div>
          )}

          {err && <div className="error-banner">{err}</div>}
        </div>

        <div className="db-modal-footer">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleAdd} disabled={saving}>
            {saving ? <LoadingDots /> : 'Add Widget'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Single live widget ────────────────────────────────────────────
function LiveWidget({ widget, dashboardId, onDelete }:
  { widget: WidgetItem; dashboardId: string; onDelete: () => void }) {
  const [data, setData] = useState<WidgetData>({ loading: true, error: null, result: null });

  const load = useCallback(async () => {
    setData(d => ({ ...d, loading: true, error: null }));
    try {
      const r = await getWidgetData(dashboardId, widget.id);
      setData({ loading: false, error: null, result: r });
    } catch (e: any) {
      setData({ loading: false, error: e.message || 'Failed', result: null });
    }
  }, [dashboardId, widget.id]);

  useEffect(() => { load(); }, [load]);

  const cfg = data.result;
  return (
    <div className="db-widget">
      <div className="db-widget-header">
        <div className="db-widget-title">
          <span>{widget.title}</span>
          <span className="widget-type-badge">{widget.chart_type}</span>
        </div>
        <div className="db-widget-actions">
          <button className="btn-icon" onClick={load} title="Refresh">↻</button>
          <button className="btn-icon" onClick={onDelete} title="Remove">✕</button>
        </div>
      </div>
      <div className="db-widget-body">
        {data.loading ? (
          <div className="db-widget-loading"><LoadingDots /></div>
        ) : data.error ? (
          <div className="db-widget-error">
            <span>⚠️ {data.error}</span>
            <button className="btn-retry" onClick={load}>Retry</button>
          </div>
        ) : cfg ? (
          <ChartContainer config={{
            type: cfg.chart_type as any,
            chart_type: cfg.chart_type !== 'table' ? cfg.chart_type as any : undefined,
            x_axis: cfg.chart_config?.x_axis,
            y_axis: cfg.chart_config?.y_axis,
            value_col: cfg.chart_config?.value_col,
            data: cfg.successful_data,
          }} />
        ) : null}
      </div>
    </div>
  );
}

// ── Main view ─────────────────────────────────────────────────────
export default function DashboardBuilderView() {
  const [dashboards, setDashboards]   = useState<DashboardItem[]>([]);
  const [active, setActive]           = useState<DashboardDetail | null>(null);
  const [queries, setQueries]         = useState<SavedQueryItem[]>([]);
  const [connections, setConnections] = useState<DBConnectionItem[]>([]);
  const [loading, setLoading]         = useState(true);
  const [showAdd, setShowAdd]         = useState(false);
  const [renaming, setRenaming]       = useState(false);
  const [newName, setNewName]         = useState('');
  const [creating, setCreating]       = useState(false);
  const [createName, setCreateName]   = useState('');
  const [createError, setCreateError] = useState('');
  const [savingConn, setSavingConn]   = useState(false);
  const [containerW, setContainerW]   = useState(() => Math.max(800, window.innerWidth - 224 - 64));
  const containerRef = useRef<HTMLDivElement>(null);
  const saveTimer    = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Measure the grid wrapper width precisely
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Set immediately on mount
    setContainerW(el.getBoundingClientRect().width);
    const obs = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w > 0) setContainerW(w);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [ds, qs, conns] = await Promise.all([getDashboards(), getSavedQueries(), getConnections()]);
      setDashboards(ds);
      setQueries(qs);
      setConnections(conns);
      if (ds.length > 0 && !active) {
        const detail = await getDashboard(ds[0].id);
        setActive(detail);
      }
    } finally { setLoading(false); }
  };

  useEffect(() => { loadAll(); }, []);

  const selectDashboard = async (id: string) => {
    setLoading(true);
    try { setActive(await getDashboard(id)); }
    finally { setLoading(false); }
  };

  const handleCreate = async () => {
    if (!createName.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const d = await createDashboard({ name: createName.trim() });
      setDashboards(prev => [d, ...prev]);
      const detail = await getDashboard(d.id);
      setActive(detail);
      setCreateName('');
    } catch (e: any) {
      setCreateError(e.message || 'Failed to create dashboard');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this dashboard and all its widgets?')) return;
    await deleteDashboard(id);
    const remaining = dashboards.filter(d => d.id !== id);
    setDashboards(remaining);
    if (active?.id === id) {
      setActive(remaining.length ? await getDashboard(remaining[0].id) : null);
    }
  };

  const handleRename = async () => {
    if (!active || !newName.trim()) return;
    const updated = await updateDashboard(active.id, { name: newName.trim() });
    setActive(prev => prev ? { ...prev, name: updated.name } : prev);
    setDashboards(prev => prev.map(d => d.id === updated.id ? { ...d, name: updated.name } : d));
    setRenaming(false);
  };

  const handleConnectionChange = async (connId: string) => {
    if (!active) return;
    setSavingConn(true);
    try {
      const payloadId = connId || null;
      await updateDashboard(active.id, { connection_id: payloadId } as any);
      setActive(prev => prev ? { ...prev, connection_id: payloadId } : prev);
    } finally { setSavingConn(false); }
  };

  const handleWidgetAdded = (w: WidgetItem) => {
    setActive(prev => prev ? { ...prev, widgets: [...prev.widgets, w] } : prev);
    setShowAdd(false);
  };

  const handleWidgetDelete = async (widgetId: string) => {
    if (!active) return;
    await deleteWidget(active.id, widgetId);
    setActive(prev => prev ? { ...prev, widgets: prev.widgets.filter(w => w.id !== widgetId) } : prev);
  };

  // Debounced layout save
  const handleLayoutChange = (layout: any) => {
    if (!active) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      const items = layout.map((l: any) => ({
        id: l.i, grid_x: l.x, grid_y: l.y, grid_w: l.w, grid_h: l.h,
      }));
      try { await saveLayout(active.id, items); } catch { /* silent */ }
    }, 800);
  };

  const gridLayout = (active?.widgets ?? []).map(w => ({
    i: w.id, x: w.grid_x, y: w.grid_y, w: w.grid_w, h: w.grid_h, minW: 3, minH: 3,
  }));

  return (
    <div className="db-builder">
      {/* ── Sidebar ── */}
      <aside className="db-sidebar">
        <div className="db-sidebar-heading">Dashboards</div>

        <div className="db-create-row">
          <input className="db-create-input" placeholder="New dashboard name…"
                 value={createName} onChange={e => setCreateName(e.target.value)}
                 onKeyDown={e => e.key === 'Enter' && handleCreate()} />
          <button className="db-create-btn" onClick={handleCreate} disabled={creating || !createName.trim()}>
            {creating ? '…' : '+'}
          </button>
        </div>
        {createError && (
          <div style={{ padding: '0 12px 8px', fontSize: '0.75rem', color: 'var(--error)' }}>
            {createError}
          </div>
        )}

        <nav className="db-nav">
          {dashboards.map(d => (
            <div key={d.id} className={`db-nav-item ${active?.id === d.id ? 'active' : ''}`}
                 onClick={() => selectDashboard(d.id)}>
              <span className="db-nav-icon">📊</span>
              <span className="db-nav-label">{d.name}</span>
              <button className="db-nav-delete" onClick={e => { e.stopPropagation(); handleDelete(d.id); }}
                      title="Delete">✕</button>
            </div>
          ))}
          {!loading && dashboards.length === 0 && (
            <div className="db-nav-empty">No dashboards yet</div>
          )}
        </nav>
      </aside>

      {/* ── Canvas ── */}
      <div className="db-canvas">
        <div className="db-canvas-inner">
        {loading ? (
          <div className="db-canvas-loading"><LoadingDots /></div>
        ) : !active ? (
          <div className="db-canvas-empty">
            <div style={{ fontSize: '3rem' }}>📊</div>
            <h3>No dashboard selected</h3>
            <p>Create a dashboard from the sidebar to get started.</p>
          </div>
        ) : (
          <>
            {/* Toolbar */}
            <div className="db-toolbar">
              <div className="db-toolbar-left">
                {renaming ? (
                  <div className="db-rename-row">
                    <input className="db-rename-input" value={newName}
                           onChange={e => setNewName(e.target.value)}
                           onKeyDown={e => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setRenaming(false); }}
                           autoFocus />
                    <button className="btn-primary-sm" onClick={handleRename}>Save</button>
                    <button className="btn-ghost-sm" onClick={() => setRenaming(false)}>Cancel</button>
                  </div>
                ) : (
                  <div className="db-title-row">
                    <h2 className="db-title">{active.name}</h2>
                    <button className="btn-icon" onClick={() => { setNewName(active.name); setRenaming(true); }}
                            title="Rename">✏️</button>
                  </div>
                )}
                <span className="db-widget-count">{active.widgets.length} widget{active.widgets.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="db-toolbar-right">
                {/* Connection picker */}
                <div className="db-conn-picker">
                  <span className="db-conn-label">🗄️</span>
                  <select
                    value={active.connection_id ?? ''}
                    onChange={e => handleConnectionChange(e.target.value)}
                    disabled={savingConn}
                    className="db-conn-select"
                    title="Select database connection for this dashboard"
                  >
                    <option value="">— Select connection —</option>
                    {connections.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.connection_name} ({c.database_name})
                      </option>
                    ))}
                  </select>
                  {savingConn && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>saving…</span>}
                  {!active.connection_id && (
                    <span className="db-conn-warning">⚠️ No connection</span>
                  )}
                </div>
                <button className="btn-primary-sm" onClick={() => setShowAdd(true)}
                        disabled={!active.connection_id}
                        title={!active.connection_id ? 'Select a connection first' : 'Add widget'}>
                  + Add Widget
                </button>
              </div>
            </div>

            {/* Grid */}
            {active.widgets.length === 0 ? (
              <div className="db-canvas-empty">
                <div style={{ fontSize: '2.5rem' }}>🧩</div>
                <h3>Empty dashboard</h3>
                <p>Click "Add Widget" to add your first chart.</p>
                <button className="btn-primary" onClick={() => setShowAdd(true)}>+ Add Widget</button>
              </div>
            ) : (
              <div
                ref={containerRef}
                style={{ width: '100%', flex: 1, minHeight: 0 }}
              >
                <GridLayout
                  className="db-grid"
                  layout={gridLayout}
                  cols={12}
                  rowHeight={80}
                  width={containerW}
                  onLayoutChange={handleLayoutChange}
                  draggableHandle=".db-widget-header"
                  margin={[16, 16]}
                >
                  {active.widgets.map(w => (
                    <div key={w.id}>
                      <LiveWidget
                        widget={w}
                        dashboardId={active.id}
                        onDelete={() => handleWidgetDelete(w.id)}
                      />
                    </div>
                  ))}
                </GridLayout>
              </div>
            )}
          </>
        )}
        </div>{/* db-canvas-inner */}
      </div>

      {/* Add widget modal */}
      {showAdd && active && (
        <AddWidgetModal
          dashboardId={active.id}
          queries={queries}
          onAdd={handleWidgetAdded}
          onClose={() => setShowAdd(false)}
        />
      )}
    </div>
  );
}
