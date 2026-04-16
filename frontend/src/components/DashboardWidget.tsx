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
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getReportData(report.id);
      // Always use axes from the API response (may be corrected by enforce_chart_logic)
      setChartConfig({
        data: res.data,
        x_axis: res.chart_config?.x_axis ?? report.chart_config.x_axis,
        y_axis: res.chart_config?.y_axis ?? report.chart_config.y_axis,
        chart_type: res.chart_type,
      });
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
          <button className="btn-icon" onClick={fetchData} title="Refresh">🔄</button>
          {onRemove && (
            <button className="btn-icon" onClick={() => onRemove(report.id)} title="Remove">✕</button>
          )}
        </div>
      </div>

      <div className="widget-content">
        {loading ? (
          <div className="widget-loading"><LoadingDots /></div>
        ) : error ? (
          <div className="widget-error">
            <span>⚠️</span>
            <p>{error}</p>
            <button className="btn-retry" onClick={fetchData}>Retry</button>
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
        <span className="widget-date">Updated: {new Date().toLocaleTimeString()}</span>
      </div>
    </div>
  );
};

export default DashboardWidget;
