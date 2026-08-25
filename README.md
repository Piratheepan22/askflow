# AskFlow

A full-stack AI chat application with a tool-calling LangChain agent, retrieval-augmented generation (RAG) over uploaded documents, JWT authentication, and a live deployment on Render.

**[Live Demo](https://askflow-1.onrender.com)** 

> Note: the live demo runs on Render's free tier, so the backend may take up to a minute to wake up on the first request after a period of inactivity.

---

## Overview

AskFlow is a chatbot whose "brain" is a LangChain agent that reasons about a user's message and decides whether to answer directly or call one of several tools — searching the web, doing math, saving notes, or retrieving relevant chunks from a document the user uploaded. Every layer of a modern full-stack product is implemented here: authenticated REST API, relational + vector data storage, an LLM agent layer, a React frontend, and a CI/CD deployment pipeline.

## Features

- **Conversational chat** with persistent history, backed by PostgreSQL
- **Tool-calling agent** (Groq-hosted LLM via LangChain) with:
  - Web search (Tavily), with parallelized multi-query search planning
  - A calculator tool
  - Note save / list / delete
  - Current date/time lookup
  - Retry logic and iteration/timeout limits to keep the agent from looping
- **Retrieval-Augmented Generation (RAG)**
  - Upload a PDF or text file
  - Text is chunked, embedded locally (`fastembed`), and stored as vectors in Postgres via `pgvector`
  - The agent retrieves and cites relevant chunks when answering questions about an uploaded document
- **Authentication** — username/password signup and login, bcrypt password hashing, JWT-based sessions; all conversations and data are scoped per user
- **Frontend**
  - Markdown rendering (tables, code blocks, GFM) in chat replies
  - Light / dark theme, persisted across sessions
  - Sidebar navigation with profile/settings
  - File upload for RAG documents

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS, react-markdown |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL + `pgvector` |
| AI / Agent | LangChain, Groq API (LLM), Tavily (web search), `fastembed` (local embeddings) |
| Auth | JWT (`python-jose`), `passlib` + `bcrypt` |
| Infra | Docker, Docker Compose (local dev), Render (hosting) |

## Architecture

```
Browser (React + Tailwind)
      |
      | HTTP / JSON
      v
FastAPI backend  --- JWT auth on protected routes
      |
      +--> PostgreSQL (conversations, messages, users, documents, chunks)
      |
      +--> LangChain agent
              |
              +--> Groq LLM (reasoning + tool selection)
              +--> Tavily (web search tool)
              +--> pgvector similarity search (RAG tool)
```

Each incoming chat message is validated, persisted, and handed to the agent along with a capped window of recent conversation history. The agent decides whether to answer directly or invoke a tool, and the final reply is persisted and returned as JSON.

## Running Locally

**Requirements:** Docker Desktop, a Groq API key, a Tavily API key.

```bash
git clone https://github.com/yourusername/askflow.git
cd askflow
cp .env.example .env
# edit .env and fill in real values (see below)
docker compose up --build
```

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Environment Variables

See [`.env.example`](.env.example) for the full list with descriptions. In short:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `GROQ_API_KEY` | LLM provider for the agent |
| `TAVILY_API_KEY` | Web search tool |
| `JWT_SECRET` | Signing secret for auth tokens (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |

## Project Structure

```
askflow/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI app, routes, auth dependency
│   │   ├── config.py       # settings from environment
│   │   ├── database.py     # SQLAlchemy engine/session
│   │   ├── models.py       # tables: User, Conversation, Message, Note, Document, Chunk
│   │   ├── schemas.py      # Pydantic request/response models + validation
│   │   ├── auth.py         # password hashing, JWT creation/verification
│   │   ├── agent.py        # LangChain agent, tools, prompt
│   │   └── rag.py          # chunking, embedding, vector search
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # chat UI, auth screen, sidebar
│   │   ├── api.js          # backend fetch helpers
│   │   └── index.css
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Deployment

The app is deployed on **Render**:
- **Backend** — Web Service, built from `backend/Dockerfile`
- **Frontend** — Static Site, built with `npm run build`
- **Database** — Render PostgreSQL with the `pgvector` extension enabled

Both services auto-deploy from `main` on every push via Render's GitHub integration.

## Known Limitations

- Conversation history sent to the LLM is capped by message count, not token count — a long individual message can still spike request size
- No email verification or password reset flow (username/password only, by design, for project scope)
- Free-tier Groq API has a daily token limit; heavy testing can hit `429` rate limits
- Free-tier Render backend spins down after inactivity, causing a slow first request
