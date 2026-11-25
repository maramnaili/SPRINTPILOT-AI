# SprintPilot AI

SprintPilot turns a software project brief into a draft backlog and sprint plan. It combines an LLM for analysis and generation with deterministic Python checks. Plans need human approval before they can be marked approved.

## Run locally (Windows)

Use Python 3.12 and run these commands from the repository folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Install [Ollama for Windows](https://ollama.com/download), then download the free local model:

```powershell
ollama pull qwen2.5:3b
```

Ollama runs the model on your computer. There is no API key or usage fee; the model download uses about 1.9 GB of disk space, and generation speed depends on your hardware. The app defaults to this local Ollama model.

Local generation can be slow. Each LLM request waits up to 300 seconds by default; change `OLLAMA_TIMEOUT_SECONDS` in `.env` if needed. The UI allows up to 11 minutes for a complete plan generation, which makes two sequential LLM requests.

The project uses the OpenAI Python package only as an HTTP client for Ollama's compatible local endpoint; it does not send requests to OpenAI.

Start the backend:

```powershell
python -m uvicorn sprintpilot.api:app --reload
```

In another terminal, activate `.venv` and start the UI:

```powershell
streamlit run src\sprintpilot\ui.py
```

The UI opens at `http://localhost:8501`. API docs are at `http://127.0.0.1:8000/docs`.

## Project layout

```text
src/sprintpilot/   Application modules
tests/             Automated tests
data/knowledge_base/ Example planning guidelines
evaluation/        Sample briefs and a small local evaluation
docs/              Original project specification
```

The Python package uses direct modules rather than a directory for every component:

- `models.py`: Pydantic data models
- `analysis.py` and `backlog.py`: structured generation through Ollama's compatible local API
- `planning.py`: estimation, dependencies, sprint assignment and review
- `workflow.py`: LangGraph workflow
- `knowledge.py`: ChromaDB retrieval
- `database.py`: SQLite persistence
- `api.py` and `ui.py`: FastAPI and Streamlit

## Verify and evaluate

```powershell
python -m pytest
python evaluation\evaluate.py
```

The tests mock model calls and do not require Ollama to be running. The sample evaluation checks input-schema validity and capacity calculation; it does not claim to measure LLM quality.


