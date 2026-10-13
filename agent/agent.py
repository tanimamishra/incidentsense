import requests
from tools import query_metrics, get_container_logs, get_container_status
from rules import classify, is_consistent

OLLAMA_URL = "http://host.docker.internal:11434"
MODEL = "qwen2.5:7b"
MAX_STEPS = 5

SYSTEM_PROMPT = (
    "You are an incident investigator for a Flask app in the container 'incidentsense-app'. "
    "A rule engine has already decided the cause category. Explain it in ONE plain sentence "
    "using the evidence provided. Do not change the category and do not mention other causes. "
    "Call a tool only if you need more evidence."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_metrics",
            "description": "Run a PromQL query on Prometheus and return the result.",
            "parameters": {
                "type": "object",
                "properties": {"promql": {"type": "string", "description": "PromQL expression"}},
                "required": ["promql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_container_logs",
            "description": "Read the most recent log lines of a container.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "container name"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_container_status",
            "description": "Check if a container is running, its exit code, restart count and OOM-kill flag.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "container name"}},
                "required": ["name"],
            },
        },
    },
]

def run_tool(name: str, args: dict) -> str:
    if name == "query_metrics":
        return query_metrics(args.get("promql", "up"))
    if name == "get_container_logs":
        return get_container_logs(args.get("name", "incidentsense-app"))
    if name == "get_container_status":
        return get_container_status(args.get("name", "incidentsense-app"))
    return f"unknown tool: {name}"

BAD_PHRASES = ["out of memory", "memory leak", "oom-kill", "oom kill", "oom killed"]

def run_llm(messages: list, trace: list) -> str:
    for step in range(1, MAX_STEPS + 1):
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": MODEL, "messages": messages, "tools": TOOLS, "stream": False},
            timeout=600,
        )
        message = response.json()["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return message.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            result = run_tool(name, args)
            trace.append({"step": step, "tool": name, "args": args, "mode": "llm"})
            print(f"STEP {step}: {name} {args}", flush=True)
            messages.append({"role": "tool", "tool_name": name, "content": result})
    return ""

def investigate(alert_text: str) -> dict:
    container = "incidentsense-app"
    status = get_container_status(container)
    up = query_metrics('up{job="flask-app"}')
    logs = get_container_logs(container, 15)

    decision = classify(status, up)
    category = decision["category"]

    evidence = (
        f"Alert: {alert_text}\n"
        f"Rule engine category: {category}\n\n"
        f"Container status: {status}\n\n"
        f"Prometheus up: {up}\n\n"
        f"Recent logs:\n{logs}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": evidence},
    ]
    trace = [
        {"step": 0, "tool": "get_container_status", "mode": "auto"},
        {"step": 0, "tool": "query_metrics", "mode": "auto"},
        {"step": 0, "tool": "get_container_logs", "mode": "auto"},
    ]

    source = "llm"
    try:
        explanation = run_llm(messages, trace).strip()
    except Exception:
        explanation = ""

    if not explanation or not is_consistent(category, explanation):
        explanation = f"Rule-based result: {category.replace('_', ' ')}."
        source = "rules"

    return {
        "category": category,
        "explanation": explanation,
        "evidence": {
            "container_status": status,
            "prometheus_up": up,
            "log_tail": logs.splitlines()[-3:],
        },
        "fix": decision["fix"],
        "explained_by": source,
        "tools_used": trace,
    }