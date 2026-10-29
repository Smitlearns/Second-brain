# Second Brain

Save notes, ideas, plans and code, then ask an AI about them.

- **frontend/**: React + TypeScript (Vite). The Notes, Ask and Dashboard pages.
- **flask_app.py**: Flask, at `/flask`. Adding notes, importing files, exporting Markdown.
- **app/main.py**: FastAPI, at `/api`. Editing notes, the Dashboard, chats and AI answers. It also serves the built React app.

## Run it

Needs Python, Node.js and [Ollama](https://ollama.com) with `llama3.2:3b` and `nomic-embed-text`.

```
pip install -r requirements.txt
python run.py
```

Then open http://localhost:5173. To serve everything from FastAPI alone, run `npm run build` in `frontend/`
and start `uvicorn app.main:app`, then open http://localhost:8000. The API docs are at `/docs`.
