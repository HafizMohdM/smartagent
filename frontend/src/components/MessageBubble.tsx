
interface Message {
    role: 'user' | 'assistant';
    content: string;
    tool_used?: string;
    timestamp: Date;
}

export default function MessageBubble({ message }: { message: Message }) {
    const isUser = message.role === 'user';
    const time = message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return (
        <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
            {!isUser && <div className="bubble-avatar">AI</div>}
            <div className="bubble-body">
                <div className="bubble-content">
                    {message.content.split('\n').map((line, i, arr) => (
                        <>
                            {line}
                            {i < arr.length - 1 && <br />}
                        </>
                    ))}
                </div>
                <div className="bubble-meta">
                    {message.tool_used && (
                        <span className="tool-badge">🔧 {message.tool_used}</span>
                    )}
                    <span className="bubble-time">{time}</span>
                </div>
            </div>
            {isUser && <div className="bubble-avatar user-avatar">You</div>}
        </div>
    );
}
