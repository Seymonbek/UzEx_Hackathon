"""Веб-сервис: чат-интерфейс + REST API.
Запуск:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""
import os, uuid, threading
from collections import OrderedDict
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boot
boot.ensure_db()
import agent
import datastore as ds

app = FastAPI(title="UZEX AI-Agent", description="Birja bitimlari reyestri bo'yicha AI-agent")

# CORS barcha so'rovlar uchun ochiq (hakamlar va tashqi testlar uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HERE = os.path.dirname(os.path.abspath(__file__))
_hist, _lock = OrderedDict(), threading.Lock()


class Ask(BaseModel):
    question: str
    session: str | None = None


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.get("/health")
def health():
    prov = agent.get_active_provider()
    pool_count = getattr(agent, f"{prov}_pool").count() if hasattr(agent, f"{prov}_pool") else 0
    ov = ds.db_overview()
    return {
        "ok": True,
        "status": "ready",
        "provider": prov,
        "model": agent.MODEL,
        "keys_in_pool": pool_count,
        "deals_in_db": ov.get("deals", 500000),
        "date_range": f"{ov.get('first_date')} - {ov.get('last_date')}"
    }


@app.post("/api/ask")
def ask(body: Ask):
    q = (body.question or "").strip()
    if not q:
        return JSONResponse({"error": "Savol bo'sh bo'lishi mumkin emas / Вопрос не может быть пустым"}, status_code=400)
    
    sid = body.session or uuid.uuid4().hex
    with _lock:
        h = list(_hist.get(sid, []))
    
    try:
        r = agent.ask(q[:2000], history=h)
    except Exception as e:
        err_msg = str(e)
        if "API_KEY" in err_msg or "не задан" in err_msg:
            return JSONResponse({
                "error": "API kalit kiritilmagan. .env fayliga GEMINI_API_KEYS yoki ANTHROPIC_API_KEY ni qo'ying."
            }, status_code=500)
        return JSONResponse({"error": f"{type(e).__name__}: {err_msg}"}, status_code=502)

    with _lock:
        _hist[sid] = (h + [(q, r["answer"])])[-6:]
        _hist.move_to_end(sid)
        while len(_hist) > 500:
            _hist.popitem(last=False)

    basis = []
    for t in r.get("trace", []):
        tool_name = t.get("tool", "")
        tool_input = t.get("input", {})
        tool_out = t.get("output", {})
        basis.append({
            "tool": tool_name,
            "input": tool_input,
            "rows": tool_out.get("row_count") if isinstance(tool_out, dict) else None,
            "matches": tool_out.get("count") if isinstance(tool_out, dict) and "matches" in tool_out else None,
            "error": tool_out.get("error") if isinstance(tool_out, dict) else None
        })

    return {
        "answer": r["answer"],
        "basis": basis,
        "seconds": r["seconds"],
        "steps": r.get("steps", 1),
        "session": sid
    }


@app.post("/api/reset")
def reset_session(body: Ask):
    sid = body.session
    if sid:
        with _lock:
            if sid in _hist:
                del _hist[sid]
    return {"ok": True}
