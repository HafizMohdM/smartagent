import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    getChatSessions,
    getChatSession,
    sendDbChatMessage,
    getConnections,
    createSavedQuery,
    type ChatSessionMetaResponse,
    type ChartConfig,
    type DBConnectionItem,
} from '../api/client';
import MessageBubble from '../components/MessageBubble';
import LoadingDots from '../components/LoadingDots';

export interface Message {
    role: 'user' | 'assistant';
    content: string;
    summary?: string;
    sql?: string;
    chart?: ChartConfig;
    metadata?: any;
    tool_used?: string;
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
    
    // Connection & Onboarding state
    const [connections, setConnections] = useState<DBConnectionItem[]>([]);
    const [loadingConnections, setLoadingConnections] = useState(true);

    // Save Query state
    const [msgToSave, setMsgToSave] = useState<Message | null>(null);
    const [saveTitle, setSaveTitle] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    const bottomRef = useRef<HTMLDivElement>(null);
    const autoExecDone = useRef(false);

    useEffect(() => {

        getConnections()
            .then(data => {
                setConnections(data);
            })
            .catch(() => setConnections([]))
            .finally(() => setLoadingConnections(false));
    }, []);


    // Load all chat sessions for this user
    const loadSessions = async () => {
        try {
            const res = await getChatSessions();
            setSessions(res);
        } catch (err) {
            console.error('Failed to load sessions:', err);
        }
    };

    useEffect(() => { 
        if (connections.length > 0) {
            loadSessions(); 
        }
    }, [connections]);

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
                const mapped: Message[] = res.messages.map(m => ({
                    role: m.role === 'agent' ? 'assistant' : 'user',
                    content: m.message_text,
                    sql: m.generated_sql || undefined,
                    metadata: m.query_result_snapshot,
                    chart: m.query_result_snapshot?.chart,
                    timestamp: new Date(m.created_at),
                }));
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

        try {
            const res = await sendDbChatMessage(
                text,
                activeSessionId,
            );

            const newSessionId = res.metadata?.session_id;
            const isNewSession = !activeSessionId && newSessionId;

            const agentMsg: Message = {
                role: 'assistant',
                content: res.agent_message.message_text,
                sql: res.agent_message.generated_sql || undefined,
                chart: res.metadata?.chart,
                metadata: res.metadata,
                tool_used: res.tool_used || undefined,
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
        setSaveTitle(currentSession?.session_name || `Query - ${new Date().toLocaleDateString()}`);
    };

    const confirmSaveQuery = async () => {
        if (!msgToSave || !saveTitle) return;
        setIsSaving(true);
        try {
            await createSavedQuery({
                connection_id: connections[0]?.id || '',
                query_name: saveTitle,
                natural_language_query: msgToSave.content,
                generated_sql: msgToSave.sql || '',
                // Requirement 10: Do not store raw result data
                query_result_snapshot: null, 
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

    const dbSuggestions = [
        'Show me all tables in the database',
        'What are the top 10 records by date?',
        'Describe the schema of the users table',
        'Count the total number of rows',
    ];

    const suggestions = dbSuggestions;

    const isConnectionRequired = !loadingConnections && connections.length === 0;

    return (
        <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
            {/* Sidebar */}
            <aside className="chat-sidebar" style={{ width: '280px', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--card-bg)' }}>
                {/* Header */}
                <div style={{ padding: '1.5rem 1rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', backgroundColor: 'var(--primary-color)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <span style={{ fontSize: '1.2rem', margin: 'auto' }}>🤖</span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: '1.1rem', letterSpacing: '-0.02em' }}>AI Analyst</div>
                </div>

                {/* New Chat button - hidden if no database connected */}
                {connections.length > 0 && (
                    <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border-color)' }}>
                        <button
                            id="new-chat-btn"
                            className="btn-accent"
                            style={{ width: '100%', padding: '0.5rem' }}
                            onClick={handleNewChat}
                        >
                            + New Chat
                        </button>
                    </div>
                )}

                {/* Session list - hidden if no database connected */}
                {connections.length > 0 ? (
                    <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
                        <div style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--text-color)', opacity: 0.5, marginBottom: '0.5rem', paddingLeft: '0.5rem' }}>
                            Chat History
                        </div>
                        {sessions.length === 0 && (
                            <div style={{ padding: '1rem', textAlign: 'center', opacity: 0.5, fontSize: '0.9rem' }}>
                                No previous chats
                            </div>
                        )}
                        {sessions.map(s => (
                            <div
                                key={s.session_id}
                                onClick={() => setActiveSessionId(s.session_id)}
                                style={{
                                    padding: '0.75rem',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    marginBottom: '0.25rem',
                                    backgroundColor: activeSessionId === s.session_id
                                        ? 'var(--primary-hover-color, rgba(99,102,241,0.1))'
                                        : 'transparent',
                                    borderLeft: activeSessionId === s.session_id
                                        ? '3px solid var(--primary-color)'
                                        : '3px solid transparent',
                                }}
                            >
                                <div style={{ fontWeight: 500, fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {s.session_name || 'Chat Session'}
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '2px' }}>
                                    <span style={{ fontSize: '0.75rem', opacity: 0.6 }}>
                                        {new Date(s.updated_at).toLocaleDateString()}{' '}
                                        {new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center', opacity: 0.4 }}>
                        <div style={{ fontSize: '0.9rem', color: 'red' }}>Connect a database to view chat history</div>
                    </div>
                )}


                {/* Back button */}
                <div style={{ padding: '1rem', borderTop: '1px solid var(--border-color)' }}>
                    <button className="btn-ghost-sm" onClick={() => navigate('/dashboard')} style={{ width: '100%' }}>
                         Back to Dashboard
                    </button>
                </div>
            </aside>

            {/* Main Chat Area */}
            <div className="chat-container" style={{ flex: 1, position: 'relative' }}>
                <div className="chat-messages">
                    {!loadingHistory && messages.length === 0 && (
                        <div className="empty-state">
                            {isConnectionRequired ? (
                                <>
                                    <div className="empty-icon-container">
                                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <rect x="5" y="4" width="14" height="16" rx="1" stroke="#1e293b" strokeWidth="2" />
                                            <path d="M5 9h14M5 15h14" stroke="#1e293b" strokeWidth="2" />
                                            <path d="M11 6.5h2M11 12.5h2M11 18.5h2" stroke="#1e293b" strokeWidth="2" strokeLinecap="round" />
                                        </svg>
                                    </div>
                                    <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1e293b', marginBottom: '8px' }}>No connections yet</h2>
                                    <p style={{ color: '#64748b', fontSize: '1rem', maxWidth: '420px', margin: '0 auto 24px', lineHeight: '1.5' }}>
                                        Add a database connection to let the AI agent query your data.
                                    </p>
                                    <button 
                                        className="btn-connect-empty"
                                        onClick={() => navigate('/connections')}
                                    >
                                        Connect a Database
                                    </button>
                                </>
                            ) : (
                                <>
                                    <div className="empty-icon">📊</div>
                                    <h2>AI Analyst</h2>
                                    <p>
                                        Ask me anything about your database. I can help with SQL queries, data visualization, and schema analysis.
                                    </p>
                                    {suggestions.length > 0 && (
                                        <div className="suggestions">
                                            {suggestions.map(s => (
                                                <button key={s} className="suggestion-chip" onClick={() => setInput(s)}>
                                                    {s}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}

                    {loadingHistory && (
                        <div style={{ padding: '2rem', textAlign: 'center' }}>
                            <LoadingDots /> Loading history...
                        </div>
                    )}

                    {messages.map((msg, i) => (
                        <MessageBubble 
                            key={i} 
                            message={msg} 
                            onSave={handleSaveQueryInitiate}
                        />
                    ))}

                    {loading && (
                        <div className="bubble bubble-assistant">
                            <div className="bubble-avatar">AI</div>
                            <div className="bubble-content">
                                <LoadingDots />
                            </div>
                        </div>
                    )}

                    <div ref={bottomRef} />
                </div>

                <form className="chat-input-bar" onSubmit={handleSubmit}>
                    <textarea
                        id="chat-input"
                        className="chat-textarea"
                        placeholder={isConnectionRequired ? "Connection Required..." : "Ask about your data... (Enter to send)"}
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        rows={1}
                        disabled={loading || loadingHistory || isConnectionRequired}
                    />
                    <button
                        id="send-btn"
                        type="submit"
                        className="btn-send"
                        disabled={!input.trim() || loading || loadingHistory || isConnectionRequired}
                        aria-label="Send message"
                    >
                        <span>⬆️</span>
                    </button>
                </form>
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
                            <input 
                                type="text"
                                className="input-field"
                                value={saveTitle}
                                onChange={e => setSaveTitle(e.target.value)}
                                placeholder="Enter title..."
                                autoFocus
                            />
                        </div>

                        <div className="modal-actions">
                            <button
                                className="btn-accent"
                                onClick={confirmSaveQuery}
                                disabled={isSaving || !saveTitle.trim()}
                            >
                                {isSaving ? 'Saving...' : 'Confirm Save'}
                            </button>
                            <button
                                className="btn-ghost"
                                onClick={() => setMsgToSave(null)}
                                disabled={isSaving}
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
