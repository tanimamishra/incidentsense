from fastapi import FastAPI, Request
from tools import query_metrics, get_container_logs, get_container_status
from llm import ask_llm
from agent import investigate
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()
    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        name = labels.get("alertname", "unknown")
        instance = labels.get("instance", "unknown")
        severity = labels.get("severity", "unknown")
        started = alert.get("startsAt", "unknown")
        print(f"ALERT {name} | instance={instance} | severity={severity} | started={started}", flush=True)
    return {"received": True}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/metrics")
def debug_metrics(q: str):
    return {"result": query_metrics(q)}
@app.get("/debug/logs")
def debug_logs(name: str):
    return {"logs": get_container_logs(name)}

@app.get("/debug/status")
def debug_status(name: str):
    return {"status": get_container_status(name)}

@app.get("/debug/llm")
def debug_llm(q: str):
    return {"reply": ask_llm(q)}

@app.get("/debug/agent")
def debug_agent(alert: str):
    return investigate(alert)