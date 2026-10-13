import requests
from tools import query_metrics, get_container_logs, get_container_status

OLLAMA_URL = "http://host.docker.internal:11434"
MODEL = "qwen2.5:7b"
MAX_STEPS = 5

SYSTEM_PROMPT = (
    "You are an incident investigator for a Flask app in the container 'incidentsense-app'. "
    "You are given collected evidence. Use only that evidence and any extra tool results. "
    "Facts you must respect: "
    "the Prometheus job name is 'flask-app'. "
    "up = 0 or running=False means the app is down. "
    "oom_killed=False means memory was NOT the cause. "
    "exit_code=137 with oom_killed=False means the container was stopped or killed from outside. "
    "exit_code=137 with oom_killed=True means it ran out of memory. "
    "Never claim a cause that the evidence does not show. "
    "Reply in exactly three lines starting with 'Cause:', 'Evidence:' and 'Fix:'."
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
    container = "incidentsense-app"
    status = get_container_status(container)
    up = query_metrics('up{job="flask-app"}')
    logs = get_container_logs(container, 15)

    evidence = (
        f"Alert: {alert_text}\n\n"
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