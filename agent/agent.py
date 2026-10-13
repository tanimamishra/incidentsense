import requests
from tools import query_metrics, get_container_logs, get_container_status

OLLAMA_URL = "http://host.docker.internal:11434"
MODEL = "qwen2.5:7b"
MAX_STEPS = 5

SYSTEM_PROMPT = (
    "You are an incident investigator. An alert fired for a Flask app running in the "
    "container 'incidentsense-app'. Use the tools to collect evidence, then explain the root cause. "
    "Useful Prometheus metrics: up, process_resident_memory_bytes, http_request_duration_seconds_sum. "
    "Reply in exactly three lines: Cause, Evidence (quote a real log line or number), Suggested fix. "
    "Never invent evidence. If tools show nothing wrong, say so."
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

def investigate(alert_text: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Alert: {alert_text}"},
    ]
    trace = []
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
            return {"answer": message.get("content", ""), "tools_used": trace}

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            result = run_tool(name, args)
            trace.append({"step": step, "tool": name, "args": args})
            print(f"STEP {step}: {name} {args}", flush=True)
            messages.append({"role": "tool", "tool_name": name, "content": result})

    return {"answer": "stopped: step limit reached", "tools_used": trace}