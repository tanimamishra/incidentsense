import requests
import docker

PROMETHEUS_URL = "http://prometheus:9090"

def query_metrics(promql: str) -> str:
    """Run a PromQL query on Prometheus and return a short text result."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=5,
        )
        results = response.json()["data"]["result"]
    except Exception as error:
        return f"query failed: {error}"

    if not results:
        return "no data"
    lines = [f"{item['metric']} -> {item['value'][1]}" for item in results[:10]]
    return "\n".join(lines)

def get_container_logs(name: str, lines: int = 30) -> str:
    """Return the last N log lines of a container."""
    try:
        client = docker.from_env()
        container = client.containers.get(name)
        return container.logs(tail=lines).decode("utf-8", errors="replace")
    except Exception as error:
        return f"could not read logs: {error}"

def get_container_status(name: str) -> str:
    """Return the state of a container: running, exit code, restarts, out-of-memory kill."""
    try:
        client = docker.from_env()
        container = client.containers.get(name)
        state = container.attrs["State"]
        return (
            f"status={state['Status']} running={state['Running']} "
            f"exit_code={state['ExitCode']} oom_killed={state['OOMKilled']} "
            f"restart_count={container.attrs['RestartCount']}"
        )
    except Exception as error:
        return f"could not read status: {error}"