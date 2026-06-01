
# RAG-Based Recommender System (Electronics)

This project is a local **Retrieval-Augmented Generation (RAG)** recommender for electronics products.
It combines:
- a cleaned product catalog
- a local Chroma vector database
- a retrieval tool exposed to an LLM agent
- a Streamlit chat UI for interactive recommendations

The default LLM backend is a local **Ollama** endpoint using `qwen2.5:3b`.

## What This Project Does

- Cleans and transforms raw Amazon electronics metadata into a searchable format.
- Builds a local ChromaDB vector index using sentence-transformer embeddings.
- Exposes a `search_catalog` tool that retrieves top product matches.
- Uses a LangGraph ReAct agent to call retrieval and compose user-friendly answers.
- Provides both:
  - a Streamlit chat interface (`app.py`)
  - terminal-based testing scripts for search and agent flow.

## Core Features

- **RAG Retrieval Pipeline**: query -> embedding search -> top matches -> LLM response.
- **Local-First Setup**: no hosted vector DB required; Chroma persists in `chroma_db/`.
- **Offline Embedding Mode**: retrieval scripts set Hugging Face offline env vars.
- **Interactive Search Validation**: test raw retrieval quality without the LLM.
- **Agent Tooling**: strict catalog search via LangGraph tool invocation.
- **Optional Supabase layer**: login/signup (`public.users`), persisted chat turns and preference-enhanced prompts (see section below).

## Project Structure

```text
RAG-Based-Recommender-System-main/
├── app.py                          # Streamlit chat app
├── main.py                         # Placeholder entry file (currently empty)
├── .env.example                    # Env template (Supabase + optional Ollama)
├── requirements.txt
├── README.md
├── auth/
│   └── supabase_auth.py            # Manual signup/signin vs public.users (+ client factory)
├── memory/
│   └── user_memory.py              # chat_history + user_preferences-backed memory
├── supabase/
│   └── schema.sql                  # DDL for Postgres (paste in SQL Editor)
├── agent/
│   ├── graph.py                    # ReAct agent creation + system prompt + CLI loop
│   └── tools.py                    # search_catalog tool backed by Chroma
├── utils/
│   ├── data_prep.py                # Converts .jsonl.gz catalog to cleaned parquet
│   ├── build_vector_db.py          # Builds Chroma index from cleaned parquet
│   └── verify_top_search.py        # Interactive retrieval sanity-check CLI
├── chroma_db/                      # Persisted local Chroma collections
└── venv/                           # Local virtual environment (workspace-specific)
```

## Detailed File Functionality

### `utils/data_prep.py`
- Streams the compressed source dataset in chunks.
- Keeps and normalizes fields: `asin`, `title`, `description`, `price`, `categories`.
- Drops rows with missing/blank titles.
- Builds `combined_text` used for semantic retrieval.
- Writes cleaned output to parquet (`data/cleaned_electronics.parquet`).

### `utils/build_vector_db.py`
- Loads cleaned parquet data.
- Creates/opens local Chroma persistent DB.
- Uses `all-MiniLM-L6-v2` embeddings.
- Inserts product documents and metadata in batches.
- Creates/updates collection: `electronics_catalog`.

### `agent/tools.py`
- Initializes Chroma persistent client from project root path.
- Loads the `electronics_catalog` collection with embedding function.
- Defines `search_catalog(query: str)` tool for the agent.
- Returns top 3 formatted product results with title, price, and category.

### `agent/graph.py`
- Defines the system prompt guiding recommendation behavior.
- Builds LangGraph ReAct agent with `ChatOpenAI` configured for local Ollama:
  - `base_url=http://localhost:11434/v1`
  - `api_key=ollama`
  - model default `qwen2.5:3b`
- Includes optional terminal chatbot mode for direct testing.

### `app.py`
- Streamlit chat interface.
- Caches agent initialization via `@st.cache_resource`.
- Maintains session chat history.
- Sends conversation to agent and displays final assistant response.

### `utils/verify_top_search.py`
- Directly queries Chroma without LLM orchestration.
- Useful to validate retrieval quality and troubleshoot index issues.

## End-to-End Setup and Execution

> Commands below are shown for **Windows PowerShell**.

### 1) Create and activate virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Start Ollama and pull model

Install Ollama first, then run:

```powershell
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

Keep Ollama available at `http://localhost:11434`.

### 4) Prepare dataset (if not already done)

Place source file at:
- `data/meta_Electronics.jsonl.gz`

Then run:

```powershell
python .\utils\data_prep.py
```

Expected output:
- `data/cleaned_electronics.parquet`

### 5) Build vector database

```powershell
python .\utils\build_vector_db.py
```

Expected output:
- Local collection in `chroma_db/` named `electronics_catalog`

### 6) Optional retrieval sanity check

```powershell
python .\utils\verify_top_search.py
```

### 7) Run the Streamlit app

```powershell
streamlit run .\app.py
```

Open the local URL printed by Streamlit (typically `http://localhost:8501`).

## Alternate Execution (Terminal Agent Loop)

If you want to test agent behavior without Streamlit:

```powershell
python .\agent\graph.py
```

Type `quit` or `exit` to stop.

## Inputs and Outputs

- **Input data**: `data/meta_Electronics.jsonl.gz` (JSON lines, gzipped)
- **Cleaned data**: `data/cleaned_electronics.parquet`
- **Vector store**: `chroma_db/`
- **UI runtime**: Streamlit app with chat session state in memory

## Notes and Troubleshooting

- If app fails with LLM connection error, verify Ollama is running.
- If retrieval fails, ensure `chroma_db/` exists and collection was built.
- `tools.py` and `verify_top_search.py` force offline embedding env vars. Make sure embedding model is available locally after first download.
- Current codebase contains PostgreSQL-related packages in dependencies, but active flow uses local Chroma persistence.

## Suggested Workflow for New Users

1. Install dependencies.
2. Ensure Ollama model is available.
3. Prepare/verify dataset files.
4. Build vector DB.
5. Validate retrieval using `verify_top_search.py`.
6. Launch `streamlit run app.py`.

---

## Supabase authentication and persistent memory (after modifications)

### Overview

- **Manual accounts** stored in Postgres table `public.users` (plaintext `password`; **development only**).
- **Chat history** in `public.chat_history` powers cross-session continuity; each turn loads recent rows into the LangGraph message list alongside the retrieval tools.
- **Preferences** live in `public.user_preferences`; their formatted summary is injected into the assistant system prompt (Chroma retrieval and ReAct wiring are unchanged).
- Streamlit talks to Supabase via `supabase-py` using **`SUPABASE_SERVICE_ROLE_KEY`** server-side only (recommended with RLS off for these demo tables unless you mint your own JWT).

### New / updated modules

| Path | Role |
|------|------|
| `auth/supabase_auth.py` | `sign_up`, `sign_in`, `sign_out`, `get_current_user_id`, shared `get_supabase_client()` |
| `memory/user_memory.py` | `save_message`, `load_history`, `update_preference`, `get_preferences`, `build_memory_context` |
| `agent/graph.py` | `invoke_recommender_with_memory(agent, user_id, user_input)`, `resolve_system_prompt_for_user` |
| `app.py` | Login / Sign-up gate, logout, hydrated chat from DB, persists turns after each reply |

### How to execute the full stack (after modifications)

```powershell
# From project root, with venv active
pip install -r requirements.txt

# 1. Run the SQL schema in Supabase (see above or supabase/schema.sql)

# 2. Configure .env (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, Ollama URLs as needed)

# 3. Ollama
ollama pull qwen2.5:3b
ollama run qwen2.5:3b

# 4. Dataset + vector index (same as earlier sections)
python .\utils\data_prep.py
python .\utils\build_vector_db.py

# 5. Launch UI (credentials required before chat appears)
streamlit run .\app.py
```

CLI loop without Supabase: `python .\agent\graph.py` remains available and does **not** persist chats (no user id).

### Preference storage

Populate rows in `public.user_preferences` manually (Dashboard → Table Editor) or call `memory.user_memory.update_preference(user_id, key, value)` from your own tooling. Preference text appears in every composed system prompt for that user via `build_memory_context()`.

### JWT / Row Level Security

If you later issue your own JWTs with a **`user_id` claim**, you can attach RLS policies that compare `auth.jwt() ->> 'user_id'` to table `user_id` instead of `auth.uid()`. See commented examples in `supabase/schema.sql`. The bundled Streamlit app uses a synthetic session token (`st.session_state["access_token"]`) for UX only; DB access continues through the backend Supabase client key unless you refactor to caller JWTs.

### Security note

Plaintext passwords are **unsafe for production**. This setup matches coursework-style requirements; migrate to hashing (bcrypt / argon2) and proper auth before deploying publicly.
