# AI Data Copilot

AI Data Copilot is an intelligent assistant designed to bridge the gap between natural language and complex database structures. It allows users to query, visualize, and manage their data using simple English, powered by advanced LLMs and semantic indexing.

## 🚀 Features

- **Natural Language to SQL**: Query your PostgreSQL databases without writing a single line of SQL.
- **Semantic Understanding**: Uses RAG and vector indexing to understand business metrics and entity relationships.
- **Dynamic Dashboards**: Visualize query results with interactive charts and tables.
- **Connection Management**: Securely manage multiple database connections with session-based isolation.
- **Autonomous Agent**: An orchestrator that can self-correct SQL errors and validate safety rules.

## 🛠️ Architecture

- **Frontend**: React + TypeScript + Vite + Recharts
- **Backend**: Python + FastAPI + SQLAlchemy (Async)
- **AI/LLM**: LangChain + OpenAI + FAISS (Vector Store)

## 📦 Getting Started

### Backend
1. `cd backend`
2. `pip install -r requirements.txt`
3. Configure your `.env` (OpenAI key, Database URL)
4. `python main.py`

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`

---

Built with ⚡ by [Antigravity](https://github.com/google-deepmind)
