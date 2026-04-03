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
    const canSave = !isUser && !!effectiveSql;

    return (
        <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
            {!isUser && <div className="bubble-avatar">AI</div>}
            <div className="bubble-body">
                <div className="bubble-content">
                    {displayContent.split('\n').map((line, i, arr) => (
                        <React.Fragment key={i}>
                            {line}
                            {i < arr.length - 1 && <br />}
                        </React.Fragment>
                    ))}
                </div>

                {!isUser && effectiveSql && (
                    <div className="sql-box">
                        <details>
                            <summary>View Generated SQL</summary>
                            <pre><code>{effectiveSql}</code></pre>
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
                            onClick={() => onSave(message)} 
                            className="btn-save-query"
                            title="Save to library"
                        >
                            💾 Save Query
                        </button>
                    )}
                </div>
            </div>
            {isUser && <div className="bubble-avatar user-avatar">You</div>}
        </div>
    );
}
