import React, { useState, useEffect } from 'react';
import {
  getSavedQueries,
  createReport,
  type SavedQueryItem,
  type ChartConfig,
} from '../api/client';
import ChartContainer from './ChartContainer';
import LoadingDots from './LoadingDots';

interface ReportBuilderProps {
  onSave: () => void;
  onCancel: () => void;
}

// ── Chart catalogue ───────────────────────────────────────────────────────────

type ChartMeta = {
  type: string;
  label: string;
  icon: string;
  group: string;
  /** which axis fields are required */
  axes: ('x' | 'y' | 'value_col')[];
};

const CHART_CATALOGUE: ChartMeta[] = [
  // Basic
  { type: 'bar',             label: 'Bar',            icon: '📊', group: 'Basic',        axes: ['x', 'y'] },
  { type: 'line',            label: 'Line',           icon: '📈', group: 'Basic',        axes: ['x', 'y'] },
  { type: 'pie',             label: 'Pie',            icon: '🥧', group: 'Basic',        axes: ['x', 'y'] },
  { type: 'table',           label: 'Table',          icon: '📄', group: 'Basic',        axes: [] },
  // Advanced
  { type: 'area',            label: 'Area',           icon: '🏔️', group: 'Advanced',     axes: ['x', 'y'] },
  { type: 'horizontal_bar',  label: 'Horiz. Bar',     icon: '↔️', group: 'Advanced',     axes: ['x', 'y'] },
  { type: 'stacked_bar',     label: 'Stacked Bar',    icon: '🗂️', group: 'Advanced',     axes: ['x', 'y'] },
  { type: 'combo',           label: 'Combo',          icon: '🔀', group: 'Advanced',     axes: ['x', 'y'] },
  // Distribution
  { type: 'histogram',       label: 'Histogram',      icon: '📉', group: 'Distribution', axes: ['x'] },
  // Relationship
  { type: 'scatter',         label: 'Scatter',        icon: '✦',  group: 'Relationship', axes: ['x', 'y'] },
  { type: 'heatmap',         label: 'Heatmap',        icon: '🌡️', group: 'Relationship', axes: ['x', 'y', 'value_col'] },
  // Hierarchy
  { type: 'treemap',         label: 'Treemap',        icon: '🗺️', group: 'Hierarchy',    axes: ['x', 'y'] },
  // KPI
  { type: 'kpi_card',        label: 'KPI Card',       icon: '🎯', group: 'KPI',          axes: ['y'] },
  { type: 'gauge',           label: 'Gauge',          icon: '⏱️', group: 'KPI',          axes: ['y'] },
];

const GROUPS = ['Basic', 'Advanced', 'Distribution', 'Relationship', 'Hierarchy', 'KPI'];

// ── helpers ───────────────────────────────────────────────────────────────────

function getSnapshotData(snapshot: any): any[] {
  if (!snapshot) return [];
  
  let s = snapshot;
  if (typeof s === 'string') {
    try { s = JSON.parse(s); } catch(e) { return []; }
  }
  
  // 1. Array-first (direct rows)
  if (Array.isArray(s)) return s;
  
  // 2. Multi-DB flat structure (new orchestrator)
  if (s.data && Array.isArray(s.data)) return s.data;
  
  // 3. Multi-DB legacy structure
  if (s.multi_db) {
    if (s.multi_db.merged_rows && Array.isArray(s.multi_db.merged_rows)) return s.multi_db.merged_rows;
    if (Array.isArray(s.multi_db.results)) return s.multi_db.results.flatMap((r: any) => r.data || []);
  }
  
  // 4. Single-DB SQLExecutor format
  if (s.rows && Array.isArray(s.rows)) return s.rows;
  
  return [];
}

function isChartable(sql: string): { ok: boolean; reason?: string } {
  const s = sql.toUpperCase();
  const hasSelectStar = /SELECT\s+\*/.test(s);
  const hasAgg = ['COUNT(', 'SUM(', 'AVG(', 'GROUP BY', 'MAX(', 'MIN('].some(k => s.includes(k));
  if (hasSelectStar && !hasAgg) {
    return { ok: false, reason: 'Query needs aggregation (COUNT, SUM, GROUP BY) for charts.' };
  }
  return { ok: true };
}

// ── component ─────────────────────────────────────────────────────────────────

const ReportBuilder: React.FC<ReportBuilderProps> = ({ onSave, onCancel }) => {
  const [queries, setQueries]               = useState<SavedQueryItem[]>([]);
  const [loadingQueries, setLoadingQueries] = useState(true);
  const [selectedQueryId, setSelectedQueryId] = useState('');
  const [previewData, setPreviewData]       = useState<SavedQueryItem | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [chartType, setChartType]           = useState('bar');
  const [xAxis, setXAxis]                   = useState('');
  const [yAxis, setYAxis]                   = useState('');
  const [valueCol, setValueCol]             = useState('');
  const [reportName, setReportName]         = useState('');
  const [saving, setSaving]                 = useState(false);
  const [error, setError]                   = useState<string | null>(null);

  useEffect(() => {
    getSavedQueries()
      .then(setQueries)
      .catch(() => setError('Failed to load saved queries.'))
      .finally(() => setLoadingQueries(false));
  }, []);

  useEffect(() => {
    if (!selectedQueryId) { setPreviewData(null); setError(null); return; }
    setLoadingPreview(true);
    setError(null);
    import('../api/client').then(({ getSavedQueryPreview }) => {
      getSavedQueryPreview(selectedQueryId)
        .then(data => {
          setPreviewData(data);
          setXAxis(''); setYAxis(''); setValueCol('');
          if (!isChartable(data.query_text).ok) setChartType('table');
        })
        .catch(() => setError('Failed to execute query. Please verify query format.'))
        .finally(() => setLoadingPreview(false));
    });
  }, [selectedQueryId]);

  const meta         = CHART_CATALOGUE.find(c => c.type === chartType)!;
  
  // ── Dynamic Execution Support ──
  // Prioritize top-level results, fallback to legacy execution snapshots
  const snapshotRows = (previewData as any)?.results || 
                       previewData?.executions?.flatMap(e => getSnapshotData(e.result_json)) || [];
                       
  const allColumns   = snapshotRows.length > 0 ? Object.keys(snapshotRows[0]) : [];
  const validation   = previewData ? isChartable(previewData.query_text) : { ok: true };

  // Determine if preview can be shown
  const axesReady = meta.axes.every(ax => {
    if (ax === 'x') return !!xAxis;
    if (ax === 'y') return !!yAxis;
    if (ax === 'value_col') return !!valueCol;
    return true;
  });
  const showPreview = !!previewData && (chartType === 'table' || (axesReady && validation.ok));

  const previewConfig: ChartConfig | null = showPreview ? {
    type: chartType as any,
    chart_type: chartType !== 'table' ? chartType as any : undefined,
    x_axis: xAxis || undefined,
    y_axis: yAxis || undefined,
    value_col: valueCol || undefined,
    data: snapshotRows,
  } : null;

  const handleSave = async () => {
    if (!reportName || !selectedQueryId) { setError('Please fill in all required fields.'); return; }
    if (chartType !== 'table' && !axesReady) { setError('Please configure all required axes.'); return; }
    if (chartType !== 'table' && !validation.ok) { setError(validation.reason!); return; }
    setSaving(true); setError(null);
    try {
      await createReport({
        report_name: reportName,
        chart_type: chartType,
        chart_config: { x_axis: xAxis, y_axis: yAxis, value_col: valueCol },
        query_id: selectedQueryId,
      });
      onSave();
    } catch (err: any) {
      setError(err.message || 'Failed to save report.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="report-builder animate-in">
      <div className="builder-header">
        <h2>Create New Report</h2>
        <p>Transform your saved queries into visual insights.</p>
      </div>

      <div className="builder-layout">
        {/* ── Left controls ── */}
        <div className="builder-controls">

          <div className="field-group">
            <label>Report Name</label>
            <input type="text" value={reportName} onChange={e => setReportName(e.target.value)}
                   placeholder="e.g., Monthly Sales Growth" />
          </div>

          <div className="field-group">
            <label>Source Query</label>
            {loadingQueries ? <LoadingDots /> : (
              <select value={selectedQueryId} onChange={e => setSelectedQueryId(e.target.value)}>
                <option value="">Select a saved query...</option>
                {queries.map(q => <option key={q.id} value={q.id}>{q.title}</option>)}
              </select>
            )}
          </div>

          {selectedQueryId && !loadingPreview && (
            <>
              {/* Chart type selector — grouped */}
              <div className="field-group">
                <label>Visualization Type</label>
                {GROUPS.map(group => {
                  const groupCharts = CHART_CATALOGUE.filter(c => c.group === group);
                  return (
                    <div key={group} style={{ marginBottom: '6px' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #888)',
                                    textTransform: 'uppercase', letterSpacing: '0.05em',
                                    marginBottom: '4px' }}>{group}</div>
                      <div className="chart-type-selector" style={{ flexWrap: 'wrap', gap: '4px' }}>
                        {groupCharts.map(c => (
                          <button
                            key={c.type}
                            className={chartType === c.type ? 'active' : ''}
                            disabled={c.type !== 'table' && !validation.ok}
                            onClick={() => { setChartType(c.type); setXAxis(''); setYAxis(''); setValueCol(''); }}
                            title={c.type !== 'table' && !validation.ok ? validation.reason : c.label}
                            style={{ fontSize: '0.75rem', padding: '4px 8px' }}
                          >
                            {c.icon} {c.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {!validation.ok && chartType !== 'table' && (
                  <p style={{ color: '#ff4d4f', fontSize: '0.8rem', marginTop: '4px' }}>
                    {validation.reason}
                  </p>
                )}
              </div>

              {/* Axis selectors — driven by chart meta */}
              {chartType !== 'table' && allColumns.length > 0 && (
                <div className="field-row" style={{ flexWrap: 'wrap', gap: '8px' }}>
                  {meta.axes.includes('x') && (
                    <div className="field-group" style={{ flex: 1, minWidth: '120px' }}>
                      <label>X-Axis</label>
                      <select value={xAxis} onChange={e => setXAxis(e.target.value)}>
                        <option value="">Select column...</option>
                        {allColumns.map(col => <option key={col} value={col}>{col}</option>)}
                      </select>
                    </div>
                  )}
                  {meta.axes.includes('y') && (
                    <div className="field-group" style={{ flex: 1, minWidth: '120px' }}>
                      <label>{chartType === 'kpi_card' || chartType === 'gauge' ? 'Value' : 'Y-Axis'}</label>
                      <select value={yAxis} onChange={e => setYAxis(e.target.value)}>
                        <option value="">Select column...</option>
                        {allColumns.map(col => <option key={col} value={col}>{col}</option>)}
                      </select>
                    </div>
                  )}
                  {meta.axes.includes('value_col') && (
                    <div className="field-group" style={{ flex: 1, minWidth: '120px' }}>
                      <label>Value Column</label>
                      <select value={valueCol} onChange={e => setValueCol(e.target.value)}>
                        <option value="">Select column...</option>
                        {allColumns.map(col => <option key={col} value={col}>{col}</option>)}
                      </select>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {loadingPreview && <LoadingDots />}
          {error && <div className="error-banner">{error}</div>}

          <div className="builder-actions">
            <button className="btn-ghost" onClick={onCancel}>Cancel</button>
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Report'}
            </button>
          </div>
        </div>

        {/* ── Right preview ── */}
        <div className="builder-preview">
          <div className="preview-label">Live Preview</div>
          <div className="preview-container">
            {showPreview && previewConfig ? (
              <ChartContainer config={previewConfig} />
            ) : previewData ? (
              <div className="preview-placeholder">
                <span className="error-icon">📊</span>
                <p>{!validation.ok && chartType !== 'table'
                  ? validation.reason
                  : 'Configure axes above to preview'}</p>
              </div>
            ) : (
              <div className="preview-placeholder">
                <span>Select a query to see a preview</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportBuilder;
