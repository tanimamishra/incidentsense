import json
from fastapi import FastAPI, Request, BackgroundTasks
from tools import query_metrics, get_container_logs, get_container_status
from llm import ask_llm
from agent import investigate
from db import init_db, save_incident, top_causes, recent_incidents
app = FastAPI()
init_db()

def handle_alert(alert_text: str):
    result = investigate(alert_text)
    save_incident(alert_text, result)
    print("INCIDENT RESULT " + json.dumps(result), flush=True)

@app.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks):
    payload = await request.json()
    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        name = labels.get("alertname", "unknown")
        instance = labels.get("instance", "unknown")
        severity = labels.get("severity", "unknown")
        started = alert.get("startsAt", "unknown")
        print(f"ALERT {name} | instance={instance} | severity={severity} | started={started}", flush=True)
        if alert.get("status") == "firing":
            background.add_task(handle_alert, f"{name} on {instance}")
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

@app.get("/stats")
def stats():
    return {"top_causes": top_causes(), "recent": recent_incidents()}
