import React, { useState, useEffect } from 'react';
import { getReportData, type ReportItem } from '../api/client';
import ChartContainer from './ChartContainer';
import LoadingDots from './LoadingDots';

interface DashboardWidgetProps {
  report: ReportItem;
  onRemove?: (id: string) => void;
}

const DashboardWidget: React.FC<DashboardWidgetProps> = ({ report, onRemove }) => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getReportData(report.id);
      setData(res.data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch report data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [report.id]);

  return (
    <div className="dashboard-widget animate-in">
      <div className="widget-header">
        <div className="widget-title">
          <h3>{report.report_name}</h3>
          <span className="widget-type-badge">{report.chart_type}</span>
        </div>
        <div className="widget-actions">
          <button className="btn-icon" onClick={fetchData} title="Refresh Live Data">🔄</button>
          {onRemove && (
            <button className="btn-icon" onClick={() => onRemove(report.id)} title="Remove Widget">✕</button>
          )}
        </div>
      </div>
      
      <div className="widget-content">
        {loading ? (
          <div className="widget-loading"><LoadingDots /></div>
        ) : error ? (
          <div className="widget-error">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
            <button className="btn-retry" onClick={fetchData}>Retry</button>
          </div>
        ) : (
          <ChartContainer 
            config={{
              type: report.chart_type,
              chart_type: report.chart_type !== 'table' ? report.chart_type : undefined,
              x_axis: report.chart_config.x_axis,
              y_axis: report.chart_config.y_axis,
              data: data
            }} 
          />
        )}
      </div>
      
      <div className="widget-footer">
        <span className="widget-date">Updated: {new Date().toLocaleTimeString()}</span>
      </div>
    </div>
  );
};

export default DashboardWidget;
