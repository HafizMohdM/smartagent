import React, { useState, useEffect } from 'react';
import { getReports, deleteReport, type ReportItem } from '../api/client';
import ReportBuilder from '../components/ReportBuilder';
import DashboardWidget from '../components/DashboardWidget';
import LoadingDots from '../components/LoadingDots';

const ReportsView: React.FC = () => {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showBuilder, setShowBuilder] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'dashboard'>('dashboard');
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getReports();
      setReports(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load reports.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this report?')) return;
    try {
      await deleteReport(id);
      setReports(reports.filter(r => r.id !== id));
    } catch (err: any) {
      alert('Delete failed: ' + err.message);
    }
  };

  if (showBuilder) {
    return (
      <div className="reports-view">
        <ReportBuilder 
          onSave={() => { setShowBuilder(false); fetchReports(); }} 
          onCancel={() => setShowBuilder(false)} 
        />
      </div>
    );
  }

  return (
    <div className="reports-view animate-in">
      <div className="view-header">
        <div className="header-info">
          <h2>Reports & Dashboards</h2>
          <p className="view-subtitle">Visualize your insights with live data widgets.</p>
        </div>
        <div className="header-actions">
          <div className="toggle-group nav-btn-group">
            <button 
              className={`nav-btn ${viewMode === 'list' ? 'nav-btn-active' : ''}`}
              onClick={() => setViewMode('list')}
            >
              List View
            </button>
            <button 
              className={`nav-btn ${viewMode === 'dashboard' ? 'nav-btn-active' : ''}`}
              onClick={() => setViewMode('dashboard')}
            >
              Dashboard
            </button>
          </div>
          <button className="btn-primary-sm create-btn" onClick={() => setShowBuilder(true)}>
            + Create Report
          </button>
        </div>
      </div>

      {loading ? (
        <div className="view-loading"><LoadingDots /></div>
      ) : error ? (
        <div className="view-error error-banner">{error}</div>
      ) : reports.length === 0 ? (
        <div className="view-empty">
          <div className="empty-icon">📊</div>
          <h3>No reports created yet</h3>
          <p>Start by creating a report from your saved queries to build your dashboard.</p>
          <button className="btn-accent" onClick={() => setShowBuilder(true)}>Create My First Report</button>
        </div>
      ) : viewMode === 'list' ? (
        <div className="reports-table-container">
          <table className="reports-table">
            <thead>
              <tr>
                <th>Report Name</th>
                <th>Type</th>
                <th>Source Query</th>
                <th>Created At</th>
                <th className="actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.id}>
                  <td className="report-name-cell">
                    <span className="report-icon">📉</span>
                    {r.report_name}
                  </td>
                  <td><span className="type-badge">{r.chart_type}</span></td>
                  <td className="source-query-cell">{r.saved_query_id}</td>
                  <td className="date-cell">{new Date(r.created_at).toLocaleDateString()}</td>
                  <td className="actions-cell">
                    <button className="btn-delete-sm" onClick={() => handleDelete(r.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="dashboard-grid">
          {reports.map(r => (
            <DashboardWidget key={r.id} report={r} onRemove={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
};

export default ReportsView;
