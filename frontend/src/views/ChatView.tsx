import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    getChatSessions,
    getChatSession,
    renameChatSession,
    deleteChatSession,
    sendDbChatMessage,
    getConnections,
    createSavedQuery,
    type ChatSessionMetaResponse,
    type ChartConfig,
    type DBConnectionItem,
    type MultiDBPayload,
} from '../api/client';
import MessageBubble from '../components/MessageBubble';
import MultiDBResults from '../components/MultiDBResults';
import LoadingDots from '../components/LoadingDots';

export interface Message {
    role: 'user' | 'assistant';
    content: string;
    summary?: string;
    sql?: string;
    chart?: ChartConfig;
    metadata?: any;
    user_query?: string;
    tool_used?: string;
    multiDb?: MultiDBPayload;
    timestamp: Date;
}

export default function ChatView() {
    const navigate = useNavigate();
    const location = useLocation();

    // Chat state
    const [sessions, setSessions] = useState<ChatSessionMetaResponse[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(false);

    // Connection state — auto-select first available, no manual picker in chat
    const [connections, setConnections] = useState<DBConnectionItem[]>([]);
    const [selectedConnectionIds, setSelectedConnectionIds] = useState<string[]>([]);
    const [loadingConnections, setLoadingConnections] = useState(true);

    // Save Query state
    const [msgToSave, setMsgToSave] = useState<Message | null>(null);
    const [saveTitle, setSaveTitle] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    // Inline rename state
    const [renamingId, setRenamingId] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState('');

    const bottomRef = useRef<HTMLDivElement>(null);
    const autoExecDone = useRef(false);

    useEffect(() => {
        getConnections()
            .then(data => {
                setConnections(data);
                const stored = localStorage.getItem('chat_selected_db_ids');
                let validIds: string[] = [];
                if (stored) {
                    try {
                        const parsed = JSON.parse(stored);
                        validIds = parsed.filter((id: string) => data.some(db => db.id === id && db.status === 'approved'));
                    } catch (err) { }
                }
                if (validIds.length === 0) {
                    const first = data.find(c => c.status === 'approved');
                    if (first) validIds = [first.id];
                }
                setSelectedConnectionIds(validIds);
            })
            .catch(() => setConnections([]))
            .finally(() => setLoadingConnections(false));
    }, []);


    // Load all chat sessions for the selected connection
    const loadSessions = async (connId?: string) => {
        const idToUse = connId || selectedConnectionIds[0];
        if (!idToUse) return;

        try {
            const res = await getChatSessions(idToUse);
            setSessions(res);
        } catch (err) {
            console.error('Failed to load sessions:', err);
        }
    };

    // Reset chat state when selection changes
    useEffect(() => {
        if (selectedConnectionIds.length > 0) {
            setActiveSessionId(null);
            setMessages([]);
            loadSessions(selectedConnectionIds[0]);
        }
    }, [selectedConnectionIds.join(',')]);

    // (Removed direct call to loadSessions here, handled by selectedConnectionId effect)

    // Handle Prefill from Saved Queries
    useEffect(() => {
        if (!autoExecDone.current && location.state?.prefillQuery && connections.length > 0 && !loadingConnections) {
            setInput(location.state.prefillQuery);
            autoExecDone.current = true;
            // Optionally trigger sendMsg here if you want it fully automatic
        }
    }, [location.state, connections, loadingConnections]);

    // Load active session messages
    useEffect(() => {
        if (!activeSessionId) {
            setMessages([]);
            return;
        }
        setLoadingHistory(true);
        getChatSession(activeSessionId)
            .then(res => {
                const mapped: Message[] = res.messages.map(m => {
                    const snapshot = m.query_result_snapshot;
                    return {
                        role: m.role === 'agent' ? 'assistant' : 'user',
                        content: m.message_text,
                        sql: m.generated_sql || snapshot?.metadata?.generated_sql || undefined,
                        metadata: snapshot,
                        chart: snapshot?.chart,
                        user_query: snapshot?.metadata?.user_query || undefined,
                        timestamp: new Date(m.created_at),
                    };
                });
                setMessages(mapped);
            })
            .catch(err => console.error('Failed to load session:', err))
            .finally(() => setLoadingHistory(false));
    }, [activeSessionId]);

    // Scroll to bottom on new message
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const handleNewChat = () => {
        setActiveSessionId(null);
        setMessages([]);
        setInput('');
    };

    const sendMsg = async () => {
        const text = input.trim();
        if (!text || loading) return;

        const userMsg: Message = { role: 'user', content: text, timestamp: new Date() };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        if (selectedConnectionIds.length === 0) {
            alert("No database connection selected.");
            setLoading(false);
            return;
        }

        try {
            const res = await sendDbChatMessage(
                text,
                selectedConnectionIds[0],
                activeSessionId,
                selectedConnectionIds,
            );

            const newSessionId = res.metadata?.session_id;
            const isNewSession = !activeSessionId && newSessionId;

            // Extract multi-DB payload if present
            const multiDb: MultiDBPayload | undefined =
                res.agent_message.query_result_snapshot?.multi_db;

            const agentMsg: Message = {
                role: 'assistant',
                content: res.agent_message.message_text,
                summary: res.agent_message.query_result_snapshot?.summary || undefined,
                sql: res.agent_message.generated_sql || res.agent_message.query_result_snapshot?.metadata?.generated_sql || undefined,
                chart: res.metadata?.chart || res.agent_message.query_result_snapshot?.chart,
                metadata: res.agent_message.query_result_snapshot,
                user_query: res.agent_message.query_result_snapshot?.metadata?.user_query || undefined,
                tool_used: res.tool_used || undefined,
                multiDb,
                timestamp: new Date(res.agent_message.created_at || new Date()),
            };
            setMessages(prev => [...prev, agentMsg]);

            if (isNewSession) {
                setActiveSessionId(newSessionId);
                loadSessions();
            }
        } catch (err: unknown) {
            const errMsg: Message = {
                role: 'assistant',
                content: `🚨 ${err instanceof Error ? err.message : 'Something went wrong processing your request.'}`,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errMsg]);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveQueryInitiate = (msg: Message) => {
        setMsgToSave(msg);
        const currentSession = sessions.find(s => s.session_id === activeSessionId);
        // Use the original user query as the default title if available
        const defaultTitle = msg.user_query || currentSession?.session_name || `Query - ${new Date().toLocaleDateString()}`;
        setSaveTitle(defaultTitle);
    };

    const confirmSaveQuery = async () => {
        if (!msgToSave || !saveTitle) return;
        setIsSaving(true);

        const currentSession = sessions.find(s => s.session_id === activeSessionId);
        const connectionId = currentSession?.connection_id || connections[0]?.id || '';

        try {
            await createSavedQuery({
                connection_id: connectionId,
                title: saveTitle,
                natural_language_query: msgToSave.content,
                query: msgToSave.sql || '',
                // Persist chart config if available, otherwise general metadata
                query_result_snapshot: msgToSave.chart ? { chart: msgToSave.chart } : msgToSave.metadata,
                row_count: msgToSave.metadata?.row_count,
            });
            setMsgToSave(null);
            alert('Saved to library.');
        } catch (err) {
            alert(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setIsSaving(false);
        }
    };

    const handleSubmit = (e: FormEvent) => { e.preventDefault(); sendMsg(); };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
    };

    const startRename = (s: ChatSessionMetaResponse, e: React.MouseEvent) => {
        e.stopPropagation();
        setRenamingId(s.session_id);
        setRenameValue(s.session_name || '');
    };

    const commitRename = async (sessionId: string) => {
        const trimmed = renameValue.trim();
        if (trimmed) {
            try {
                await renameChatSession(sessionId, trimmed);
                setSessions(prev => prev.map(s =>
                    s.session_id === sessionId ? { ...s, session_name: trimmed } : s
                ));
            } catch { /* silent */ }
        }
        setRenamingId(null);
    };

    const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!window.confirm("Are you sure you want to delete this chat session?")) return;

        try {
            console.log("Deleting session:", sessionId);
            await deleteChatSession(sessionId);
            setSessions(prev => prev.filter(s => s.session_id !== sessionId));
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
                setMessages([]);
            }
        } catch (err) {
            console.error("Delete failed:", err);
            alert("Failed to delete session");
        }
    };

    const dbSuggestions = [
        'Analyze employee attendance patterns',
        'Compare sales performance across regions',
        'Identify top 10 customers by revenue',
        'Summarize recent inventory changes'
    ];

    const suggestions = dbSuggestions;

    const isConnectionRequired = !loadingConnections && connections.filter(c => c.status === 'approved').length === 0;
    const approvedConnections = connections.filter(c => c.status === 'approved');

    return (
        <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>

            {/* ── Sidebar ── */}
            <aside className="app-sidebar">
                <div style={{ padding: '18px 14px 14px', borderBottom: '1px solid var(--sidebar-border)', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', flexShrink: 0 }}>🤖</div>
                    <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>AI Analyst</span>
                </div>

                {connections.length > 0 && (
                    <button className="btn-accent" style={{ width: '100%', padding: '8px 12px', textAlign: 'left' }} onClick={handleNewChat}>
                        + New Chat
                    </button>
                )}

                <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
                    {/* Pending connections notice */}
                    {connections.filter(c => c.status === 'pending').length > 0 && (
                        <div style={{
                            margin: '8px 8px 4px', padding: '8px 10px', background: 'rgba(245,158,11,0.12)',
                            border: '1px solid rgba(245,158,11,0.25)', borderRadius: '8px',
                            fontSize: '0.75rem', color: '#f59e0b'
                        }}>
                            ⏳ {connections.filter(c => c.status === 'pending').length} connection(s) awaiting approval
                        </div>
                    )}

                    {approvedConnections.length > 0 ? (
                        <>
                            <div style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--sidebar-muted)', padding: '10px 8px 4px' }}>
                                History
                            </div>
                            {sessions.length === 0 ? (
                                <div style={{ padding: '16px 8px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--sidebar-muted)' }}>No previous chats</div>
                            ) : sessions.map(s => (
                                <div key={s.session_id}
                                    className={`chat-session-item ${activeSessionId === s.session_id ? 'active' : ''}`}
                                    onClick={() => renamingId !== s.session_id && setActiveSessionId(s.session_id)}>
                                    {renamingId === s.session_id ? (
                                        <input
                                            autoFocus
                                            value={renameValue}
                                            onChange={e => setRenameValue(e.target.value)}
                                            onBlur={() => commitRename(s.session_id)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter') commitRename(s.session_id);
                                                if (e.key === 'Escape') setRenamingId(null);
                                            }}
                                            onClick={e => e.stopPropagation()}
                                            style={{
                                                width: '100%', background: 'rgba(255,255,255,0.1)',
                                                border: '1px solid rgba(255,255,255,0.3)', borderRadius: '5px',
                                                color: '#fff', padding: '3px 7px', fontSize: '0.85rem',
                                                outline: 'none', fontFamily: 'inherit',
                                            }}
                                        />
                                    ) : (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', overflow: 'hidden' }}>
                                            <div className="session-name" style={{ flex: 1 }}>
                                                {s.session_name || 'Chat Session'}
                                            </div>
                                            <div className="session-action-btns">
                                                <button
                                                    onClick={e => startRename(s, e)}
                                                    title="Rename"
                                                    className="session-item-btn"
                                                >✏️</button>
                                                <button
                                                    onClick={e => handleDeleteSession(s.session_id, e)}
                                                    title="Delete"
                                                    className="session-item-btn delete-btn"
                                                >🗑️</button>
                                            </div>
                                        </div>
                                    )}
                                    <div className="session-date">
                                        {new Date(s.updated_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}{' '}
                                        {new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </div>
                                </div>
                            ))}
                        </>
                    ) : (
                        <div style={{ padding: '24px 12px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--sidebar-muted)' }}>
                            {connections.length > 0
                                ? 'No approved connections yet.\nAsk an admin to approve your connection.'
                                : 'Connect a database to start chatting'}
                        </div>
                    )}
                </div>

                <div style={{ padding: '10px 12px', borderTop: '1px solid var(--sidebar-border)' }}>
                    <button className="btn-ghost-sm" onClick={() => navigate('/dashboard')} style={{ width: '100%' }}>
                        ← Dashboard
                    </button>
                </div>
            </aside>

            {/* ── Main chat area ── */}
            <div className="chat-container">
                <div className="chat-thread-focus">
                    <div className="chat-messages">
                        {!loadingHistory && messages.length === 0 && (
                            <div className="empty-state">
                                {isConnectionRequired ? (
                                    <>
                                        <div className="empty-icon">🗄️</div>
                                        <h2>{connections.length > 0 ? 'No approved connections' : 'No connections yet'}</h2>
                                        <p>{connections.length > 0
                                            ? 'Your connections are pending admin approval. Check back soon.'
                                            : 'Add a database connection to let the AI agent query your data.'}</p>
                                        <button className="btn-connect-empty" onClick={() => navigate('/dashboard')}>
                                            Go to Connections
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <div className="empty-icon">✨</div>
                                        <h2>How can I help you?</h2>
                                        <p>Ask me anything about your database — queries, analysis, or schema exploration.</p>
                                        <div className="suggestions">
                                            {suggestions.map(s => (
                                                <button key={s} className="suggestion-chip" onClick={() => setInput(s)}>{s}</button>
                                            ))}
                                        </div>
                                    </>
                                )}
                            </div>
                        )}

                        {loadingHistory && (
                            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                                <LoadingDots />
                            </div>
                        )}

                        {messages.map((msg, i) => (
                            <div key={i}>
                                <MessageBubble message={msg} onSave={handleSaveQueryInitiate} />
                                {msg.multiDb && <MultiDBResults payload={msg.multiDb} />}
                            </div>
                        ))}

                        {loading && (
                            <div className="bubble bubble-assistant">
                                <div className="bubble-avatar">AI</div>
                                <div className="bubble-content"><LoadingDots /></div>
                            </div>
                        )}

                        <div ref={bottomRef} />
                    </div>

                    <form className="chat-input-bar" onSubmit={handleSubmit}>
                        <textarea
                            className="chat-textarea"
                            placeholder={isConnectionRequired ? 'Connect a database first…' : 'Ask about your data…'}
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            rows={1}
                            disabled={loading || loadingHistory || isConnectionRequired}
                        />
                        <button type="submit" className="btn-send"
                            disabled={!input.trim() || loading || loadingHistory || isConnectionRequired}
                            aria-label="Send">
                            ↑
                        </button>
                    </form>
                </div>
            </div>

            {/* Save Query Modal */}
            {msgToSave && (
                <div className="modal-overlay">
                    <div className="modal-content" style={{ maxWidth: '400px' }}>
                        <span className="modal-icon">💾</span>
                        <h2>Save to Library</h2>
                        <p>Give this query a title to save it to your library.</p>
                        <div style={{ margin: '1.5rem 0' }}>
                            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 500 }}>Query Title</label>
                            <input type="text" className="input-field" value={saveTitle}
                                onChange={e => setSaveTitle(e.target.value)} placeholder="Enter title…" autoFocus />
                        </div>
                        <div className="modal-actions">
                            <button className="btn-accent" onClick={confirmSaveQuery} disabled={isSaving || !saveTitle.trim()}>
                                {isSaving ? 'Saving…' : 'Confirm Save'}
                            </button>
                            <button className="btn-ghost" onClick={() => setMsgToSave(null)} disabled={isSaving}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
