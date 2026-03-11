import { useState, useEffect, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { sendMessage, getChatHistory, type HistoryMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import MessageBubble from '../components/MessageBubble';
import LoadingDots from '../components/LoadingDots';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    tool_used?: string;
    timestamp: Date;
}

export default function ChatView() {
    const { sessionId, dbConnected } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [historyLoaded, setHistoryLoaded] = useState(false);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Load chat history on mount
    useEffect(() => {
        if (!sessionId) return;
        getChatHistory(sessionId)
            .then(res => {
                const mapped: Message[] = res.messages.map((m: HistoryMessage) => ({
                    role: m.role,
                    content: m.content,
                    timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
                }));
                if (mapped.length > 0) setMessages(mapped);
            })
            .catch(() => {/* no history yet — that's fine */ })
            .finally(() => setHistoryLoaded(true));
    }, [sessionId]);

    // Scroll to bottom on new message
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loading]);

    const sendMsg = async () => {
        const text = input.trim();
        if (!text || loading || !sessionId) return;

        const userMsg: Message = { role: 'user', content: text, timestamp: new Date() };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const res = await sendMessage(text, sessionId);
            const agentMsg: Message = {
                role: 'assistant',
                content: res.response,
                tool_used: res.tool_used,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, agentMsg]);
        } catch (err: unknown) {
            const errMsg: Message = {
                role: 'assistant',
                content: `⚠️ ${err instanceof Error ? err.message : 'Something went wrong'}`,
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errMsg]);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        sendMsg();
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMsg();
        }
    };

    const suggestions = [
        'Show me all tables in the database',
        'What are the top 10 records by date?',
        'Describe the schema of the users table',
        'Count the total number of rows',
    ];

    return (
        <div className="chat-container">
            <div className="chat-messages">
                {historyLoaded && messages.length === 0 && (
                    <div className="empty-state">
                        <div className="empty-icon">💬</div>
                        <h2>Ask anything about your data</h2>
                        <p>
                            {dbConnected
                                ? 'Your database is connected. Start asking questions in natural language.'
                                : 'No database connected yet — you can still chat with the AI agent.'}
                        </p>
                        <div className="suggestions">
                            {suggestions.map(s => (
                                <button key={s} className="suggestion-chip" onClick={() => setInput(s)}>
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <MessageBubble key={i} message={msg} />
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
                    placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    disabled={loading}
                />
                <button
                    id="send-btn"
                    type="submit"
                    className="btn-send"
                    disabled={!input.trim() || loading}
                    aria-label="Send message"
                >
                    <span>↑</span>
                </button>
            </form>
        </div>
    );
}
