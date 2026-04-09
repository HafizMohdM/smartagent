import React, { useState, useEffect } from 'react';
import { 
  getSavedQueries, 
  createReport, 
  type SavedQueryItem,
  type ChartConfig
} from '../api/client';
import ChartContainer from './ChartContainer';
import LoadingDots from './LoadingDots';

interface ReportBuilderProps {
  onSave: () => void;
  onCancel: () => void;
}

const ReportBuilder: React.FC<ReportBuilderProps> = ({ onSave, onCancel }) => {
  const [queries, setQueries] = useState<SavedQueryItem[]>([]);
  const [loadingQueries, setLoadingQueries] = useState(true);
  
  // Selection State
  const [selectedQueryId, setSelectedQueryId] = useState<string>('');
  const [previewData, setPreviewData] = useState<SavedQueryItem | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [chartType, setChartType] = useState<'bar' | 'line' | 'pie' | 'table'>('bar');
  const [xAxis, setXAxis] = useState<string>('');
  const [yAxis, setYAxis] = useState<string>('');
  const [reportName, setReportName] = useState<string>('');
  
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSavedQueries()
      .then(setQueries)
      .catch(() => setError('Failed to load saved queries.'))
      .finally(() => setLoadingQueries(false));
  }, []);

  // Requirement 2: Fetch preview on selection
  useEffect(() => {
    if (!selectedQueryId) {
      setPreviewData(null);
      setError(null);
      return;
    }

    const query = queries.find(q => q.id === selectedQueryId);
    if (query && !query.query) {
        setError('Invalid query. Please select a valid saved query.');
        setPreviewData(null);
        return;
    }

    setLoadingPreview(true);
    setError(null);
    
    import('../api/client').then(({ getSavedQueryPreview }) => {
      getSavedQueryPreview(selectedQueryId)
        .then(data => {
          setPreviewData(data);
          // Requirement 2: Reset axes when query changes
          setXAxis('');
          setYAxis('');
          
          // Requirement 1: Force table mode if not chartable
          const validation = isChartable(data.query);
          if (!validation.ok) {
            setChartType('table');
          }
          
          // Requirement 8: Debug Logging
          console.log('[ReportBuilder] Query Selected:', data.title);
          console.log('[ReportBuilder] SQL:', data.query);
          const columns = Object.keys(getSnapshotData(data.query_result_snapshot)[0] || {});
          console.log('[ReportBuilder] Extracted Columns:', columns);
        })
        .catch(err => {
            console.error('[ReportBuilder] Preview Error:', err);
            // Requirement 3: Clean error message
            setError('Failed to execute query. Please verify query format.');
        })
        .finally(() => setLoadingPreview(false));
    });
  }, [selectedQueryId, queries]);

  const selectedQuery = queries.find(q => q.id === selectedQueryId);
  
  // Robustly extract columns from various snapshot formats (raw array, .data, or .rows)
  const getSnapshotData = (snapshot: any) => {
    if (!snapshot) return [];
    if (Array.isArray(snapshot)) return snapshot;
    if (snapshot.data && Array.isArray(snapshot.data)) return snapshot.data;
    if (snapshot.rows && Array.isArray(snapshot.rows)) return snapshot.rows;
    return [];
  };

  // Requirement 1: SQL Aggregation Check
  const isChartable = (sql: string): { ok: boolean; reason?: string } => {
    const s = sql.toUpperCase();
    // Regex to find "SELECT *" more robustly
    const hasSelectStar = /SELECT\s+\*/i.test(s);
    // Common aggregation keywords
    const aggregationKeywords = ['COUNT(', 'SUM(', 'AVG(', 'GROUP BY', 'MAX(', 'MIN('];
    const hasAggregation = aggregationKeywords.some(kw => s.includes(kw));
    
    if (hasSelectStar && !hasAggregation) {
      return { ok: false, reason: 'This query is not suitable for visualization. Please use aggregated data (COUNT, SUM, GROUP BY).' };
    }
    return { ok: true };
  };

  const snapshotRows = getSnapshotData(previewData?.query_result_snapshot);
  const availableColumns = snapshotRows.length > 0 ? Object.keys(snapshotRows[0]) : [];
  const validation = previewData ? isChartable(previewData.query) : { ok: true };

  const handleSave = async () => {
    // Requirement 3: Axis Validation
    if (!reportName || !selectedQueryId) {
      setError('Please fill in all required fields.');
      return;
    }

    if (chartType !== 'table' && (!xAxis || !yAxis)) {
      setError('Please select X and Y axis');
      return;
    }

    if (chartType !== 'table' && !validation.ok) {
      setError(validation.reason!);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await createReport({
        report_name: reportName,
        chart_type: chartType,
        chart_config: { x_axis: xAxis, y_axis: yAxis },
        saved_query_id: selectedQueryId,
        connection_id: previewData!.connection_id
      });
      onSave();
    } catch (err: any) {
      setError(err.message || 'Failed to save report.');
    } finally {
      setSaving(false);
    }
  };

  // Requirement 8: Logging
  useEffect(() => {
    if (previewData && xAxis && yAxis) {
        console.log('[ReportBuilder] Preview Update:', {
            x: xAxis,
            y: yAxis,
            rows: snapshotRows.length
        });
    }
  }, [xAxis, yAxis, snapshotRows]);

  // Requirement 3: Preview Logic
  const showPreview = previewData && (chartType === 'table' || (xAxis && yAxis && validation.ok));

  const previewConfig: ChartConfig | null = showPreview ? {
    type: chartType,
    chart_type: chartType !== 'table' ? chartType : undefined,
    x_axis: xAxis,
    y_axis: yAxis,
    data: snapshotRows
  } : null;

  return (
    <div className="report-builder animate-in">
      <div className="builder-header">
        <h2>Create New Report</h2>
        <p>Transform your saved queries into visual insights.</p>
      </div>

      <div className="builder-layout">
        <div className="builder-controls">
          <div className="field-group">
            <label>Report Name</label>
            <input 
              type="text" 
              value={reportName} 
              onChange={e => setReportName(e.target.value)} 
              placeholder="e.g., Monthly Sales Growth"
            />
          </div>

          <div className="field-group">
            <label>Source Query</label>
            {loadingQueries ? <LoadingDots /> : (
              <select value={selectedQueryId} onChange={e => setSelectedQueryId(e.target.value)}>
                <option value="">Select a saved query...</option>
                {queries.map(q => (
                  <option key={q.id} value={q.id}>{q.title}</option>
                ))}
              </select>
            )}
          </div>

          {selectedQueryId && (
            <>
              {loadingPreview ? <LoadingDots /> : (
                <div className="field-group">
                  <label>Visualization Type</label>
                  <div className="chart-type-selector">
                    {(['bar', 'line', 'pie', 'table'] as const).map(t => (
                      <button 
                        key={t}
                        className={chartType === t ? 'active' : ''}
                        disabled={t !== 'table' && !validation.ok}
                        onClick={() => setChartType(t)}
                        title={t !== 'table' && !validation.ok ? validation.reason : ''}
                      >
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </button>
                    ))}
                  </div>
                  {!validation.ok && chartType !== 'table' && (
                    <p className="validation-warning" style={{ color: '#ff4d4f', fontSize: '0.8rem', marginTop: '4px' }}>
                      {validation.reason}
                    </p>
                  )}
                </div>
              )}

              {chartType !== 'table' && (
                <div className="field-row">
                  <div className="field-group">
                    <label>X-Axis (Label)</label>
                    <select value={xAxis} onChange={e => setXAxis(e.target.value)}>
                      <option value="">Select column...</option>
                      {availableColumns.map(col => <option key={col} value={col}>{col || 'Unnamed'}</option>)}
                    </select>
                  </div>
                  <div className="field-group">
                    <label>Y-Axis (Value)</label>
                    <select value={yAxis} onChange={e => setYAxis(e.target.value)}>
                      <option value="">Select column...</option>
                      {availableColumns.map(col => <option key={col} value={col}>{col || 'Unnamed'}</option>)}
                    </select>
                  </div>
                </div>
              )}
            </>
          )}

          {error && <div className="error-banner">{error}</div>}

          <div className="builder-actions">
            <button className="btn-ghost" onClick={onCancel}>Cancel</button>
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Report'}
            </button>
          </div>
        </div>

        <div className="builder-preview">
          <div className="preview-label">Live Preview</div>
          <div className="preview-container">
            {showPreview ? (
              <ChartContainer config={previewConfig!} />
            ) : selectedQuery ? (
              <div className="preview-placeholder validation-error">
                <span className="error-icon">📊</span>
                {(!validation.ok && chartType !== 'table') ? (
                    <p style={{ color: '#ff4d4f' }}>{validation.reason}</p>
                ) : (
                    <p>Please select X and Y axis to generate chart</p>
                )}
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
