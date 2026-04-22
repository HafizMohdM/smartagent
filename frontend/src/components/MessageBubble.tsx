import React from 'react';
import type { Message } from '../views/ChatView';
import ChartContainer from './ChartContainer';

export default function MessageBubble({ message, onSave }: { message: Message, onSave?: (msg: Message) => void }) {
    const isUser = message.role === 'user';
    const time = message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // For assistant messages, we prefer summary. For user messages, we use content.
    const displayContent = !isUser && message.summary ? message.summary : message.content;

    // Use SQL from message root or metadata fallback
    const effectiveSql = message.sql || message.metadata?.generated_sql || message.metadata?.sql;
    const isMultiDb = !!message.multiDb || message.tool_used === 'multi_db_query';
    const canSave = !isUser && (!!effectiveSql || !!message.chart || message.tool_used === 'database_query' || isMultiDb);

    // Extract table data if available
    const tableData = message.metadata?.data;
    const hasTable = !isUser && tableData && Array.isArray(tableData.rows) && tableData.rows.length > 0;

    return (
        <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
            {!isUser && (
                <div className="bubble-avatar">
                    <span style={{ fontSize: '1.1rem' }}>✨</span>
                </div>
            )}
            <div className="bubble-body">
                <div className="bubble-content">
                    {displayContent.split('\n').map((line, i, arr) => (
                        <React.Fragment key={i}>
                            {line}
                            {i < arr.length - 1 && <br />}
                        </React.Fragment>
                    ))}
                </div>

                {/* Requirement 2 & 3: Show Table Results if present */}
                {hasTable && (
                    <div className="chat-table-container">
                        <table className="chat-data-table">
                            <thead>
                                <tr>
                                    {tableData.columns.map((col: string) => (
                                        <th key={col}>{col}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {tableData.rows.slice(0, 5).map((row: any, i: number) => (
                                    <tr key={i}>
                                        {tableData.columns.map((col: string) => (
                                            <td key={col}>{String(row[col] ?? '')}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {tableData.rows.length > 5 && (
                            <div className="table-footer">
                                Showing 5 of {tableData.rows.length} rows. Save to library for full access.
                            </div>
                        )}
                    </div>
                )}

                {/* Requirement 3: View SQL Toggle (Optional, Hidden) */}
                {!isUser && effectiveSql && (
                    <div className="sql-box">
                        <details className="sql-details">
                            <summary className="sql-summary">View SQL Query</summary>
                            <pre className="sql-pre"><code>{effectiveSql}</code></pre>
                        </details>
                    </div>
                )}

                {!isUser && message.chart && (
                    <ChartContainer config={message.chart} />
                )}

                <div className="bubble-meta">
                    {message.tool_used && (
                        <span className="tool-badge">🔧 {message.tool_used}</span>
                    )}
                    {message.metadata?.row_count !== undefined && (
                        <span className="metadata-badge">📊 {message.metadata.row_count} rows</span>
                    )}
                    <span className="bubble-time">{time}</span>

                    {canSave && onSave && (
                        <button
                            onClick={(e) => { e.stopPropagation(); onSave(message); }}
                            className="btn-save-query active"
                            title="Save this query to your library"
                        >
                            💾 Save to Library
                        </button>
                    )}
                </div>
            </div>
            {isUser && (
                <div className="bubble-avatar user-avatar">
                    <span style={{ fontSize: '1rem' }}>👤</span>
                </div>
            )}
        </div>
    );
}
