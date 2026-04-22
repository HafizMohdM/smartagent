import React, { useState, useEffect } from 'react';
import { getReportData, type ReportItem } from '../api/client';
import ChartContainer from './ChartContainer';
import LoadingDots from './LoadingDots';

interface DashboardWidgetProps {
  report: ReportItem;
  onRemove?: (id: string) => void;
}

const DashboardWidget: React.FC<DashboardWidgetProps> = ({ report, onRemove }) => {
  const [chartConfig, setChartConfig] = useState<{
    data: any[];
    x_axis: string;
    y_axis: string;
    chart_type: string;
    cache_status?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [failedSources, setFailedSources] = useState<{id: string, database_name?: string, error: string}[]>([]);
  const [isLive, setIsLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchData = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await getReportData(report.id);
      
      setChartConfig({
        data: res.results.rows,
        x_axis: res.chart_config?.x_axis ?? report.chart_config.x_axis,
        y_axis: res.chart_config?.y_axis ?? report.chart_config.y_axis,
        chart_type: res.chart_type,
        cache_status: res.cache_status,
      });
      setFailedSources(res.results.meta.failed_sources || []);

      setLastUpdated(new Date());
    } catch (err: any) {
      // Guarantee 4: Handle 413 structured payload
      if (err.message && err.message.includes('too large')) {
         setError(`${err.message}. ${err.suggestion || 'Try reducing the time range or applying row limits.'}`);
      } else {
         setError(err.message || 'Failed to fetch report data.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchData();
  }, [report.id]);

  // Real-time refresh loop
  useEffect(() => {
    if (!isLive) return;

    const interval = setInterval(() => {
      // Pause if tab is inactive to save resources
      if (document.hidden) {
        console.log(`[Dashboard] Refresh paused for '${report.report_name}' (tab hidden)`);
        return;
      }
      fetchData(true);
    }, 30000); // 30 second default

    return () => clearInterval(interval);
  }, [isLive, report.id]);

  return (
    <div className={`dashboard-widget animate-in ${isLive ? 'live-border' : ''}`}>
      <div className="widget-header">
        <div className="widget-title">
          <h3>{report.report_name}</h3>
          <div className="widget-meta-tags">
             <span className="widget-type-badge">{report.chart_type}</span>
             {isLive && <span className="live-pill">LIVE</span>}
          </div>
        </div>
        <div className="widget-actions">
          <label className="switch-toggle" title="Auto-refresh (30s)">
            <input 
              type="checkbox" 
              checked={isLive} 
              onChange={(e) => setIsLive(e.target.checked)} 
            />
            <span className="slider round"></span>
          </label>
          <button className="btn-icon" onClick={() => fetchData()} title="Refresh Now">🔄</button>
          {onRemove && (
            <button className="btn-icon" onClick={() => onRemove(report.id)} title="Remove">✕</button>
          )}
        </div>
      </div>

      <div className="widget-content">
        {/* Guarantee 6: Persistent Failure Banner */}
        {failedSources.length > 0 && (
          <div className="partial-failure-persistent">
            <div className="failure-banner-header">
              <span>⚠️ Partial Data: {failedSources.length} source(s) skipped</span>
            </div>
            <ul className="failure-list">
                {failedSources.map((f: any, i: number) => {
                  // Clean user-facing message based on structured reason
                  let message: string;
                  if (f.reason === 'TABLE_NOT_FOUND') {
                    const tables = Array.isArray(f.details) ? f.details.join(', ') : f.details;
                    message = `Skipped: table(s) "${tables}" not found in this database.`;
                  } else if (f.reason === 'TIMEOUT') {
                    message = 'Skipped: query timed out.';
                  } else {
                    message = 'Execution error. Contact support if this persists.';
                  }
                  return (
                    <li key={i} title={f.error || ''}>
                      <strong>{f.database_name || f.id}:</strong> {message}
                    </li>
                  );
                })}
            </ul>
          </div>
        )}

        {loading && !chartConfig ? (
          <div className="widget-loading"><LoadingDots /></div>
        ) : error ? (
          <div className="widget-error-hardened">
            <span className="error-icon">🚫</span>
            <div className="error-body">
              <p className="error-msg">{error}</p>
              <button className="btn-retry-modern" onClick={() => fetchData()}>Retry</button>
            </div>
          </div>
        ) : chartConfig ? (
          <ChartContainer
            config={{
              type: chartConfig.chart_type as any,
              chart_type: chartConfig.chart_type !== 'table' ? chartConfig.chart_type as any : undefined,
              x_axis: chartConfig.x_axis,
              y_axis: chartConfig.y_axis,
              data: chartConfig.data,
            }}
          />
        ) : null}
      </div>

      <div className="widget-footer">
        <div className="footer-left">
           <span className="widget-date">Updated: {lastUpdated.toLocaleTimeString()}</span>
           {chartConfig?.cache_status === 'HIT' && <span className="cache-badge">Cached</span>}
        </div>
        {chartConfig && (
          <span className="row-count-badge">{chartConfig.data.length.toLocaleString()} rows</span>
        )}
      </div>
    </div>
  );
};



export default DashboardWidget;
