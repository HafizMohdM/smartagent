import { useState } from 'react';
import type { MultiDBPayload, MultiDBResult } from '../api/client';

interface Props { payload: MultiDBPayload; }

function DBResultPanel({ result }: { result: MultiDBResult }) {
  if (result.error) {
    return (
      <div className="mdb-panel mdb-error">
        <div className="mdb-panel-header">
          <span className="mdb-db-name">🗄️ {result.database}</span>
          <span className="mdb-badge error">Error</span>
        </div>
        <div className="mdb-error-msg">⚠️ {result.error}</div>
      </div>
    );
  }

  return (
    <div className="mdb-panel">
      <div className="mdb-panel-header">
        <span className="mdb-db-name">🗄️ {result.database}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="mdb-badge success">{result.row_count} rows</span>
          <span className="mdb-badge neutral">{result.execution_ms}ms</span>
        </div>
      </div>

      {result.sql && (
        <details className="mdb-sql-details">
          <summary>View SQL</summary>
          <pre className="sql-pre"><code>{result.sql}</code></pre>
        </details>
      )}

      <div className="table-preview-container" style={{ maxHeight: '280px', overflowY: 'auto' }}>
        <table className="preview-table">
          <thead>
            <tr>{result.columns.map(c => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {result.data.slice(0, 100).map((row, i) => (
              <tr key={i}>
                {result.columns.map(c => <td key={c}>{String(row[c] ?? '')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function MultiDBResults({ payload }: Props) {
  const [activeTab, setActiveTab] = useState<string>(
    payload.merged ? '__merged__' : (payload.results[0]?.database ?? '')
  );

  const tabs = [
    ...(payload.merged ? [{ key: '__merged__', label: '🔀 Merged' }] : []),
    ...payload.results.map(r => ({ key: r.database, label: `🗄️ ${r.database}` })),
  ];

  return (
    <div className="mdb-container">
      <div className="mdb-header">
        <span className="mdb-title">Multi-Database Results</span>
        <span className="mdb-count">{payload.results.length} databases queried</span>
      </div>

      {/* Tabs */}
      <div className="mdb-tabs">
        {tabs.map(t => (
          <button key={t.key}
            className={`mdb-tab ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === '__merged__' && payload.merged_rows ? (
        <div className="mdb-panel">
          <div className="mdb-panel-header">
            <span className="mdb-db-name">🔀 Merged Results</span>
            <span className="mdb-badge success">{payload.merged_rows.length} rows</span>
          </div>
          <div className="table-preview-container" style={{ maxHeight: '300px', overflowY: 'auto' }}>
            <table className="preview-table">
              <thead>
                <tr>{(payload.merged_columns ?? []).map(c => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {payload.merged_rows.slice(0, 200).map((row, i) => (
                  <tr key={i}>
                    {(payload.merged_columns ?? []).map(c => <td key={c}>{String(row[c] ?? '')}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        payload.results
          .filter(r => r.database === activeTab)
          .map(r => <DBResultPanel key={r.database} result={r} />)
      )}
    </div>
  );
}
