import re

FIXES = {
    "memory_leak_oom": "Container hit its memory limit. Check for a memory leak, then raise the limit or fix the leak.",
    "stopped_externally": "Container was stopped from outside. Check who ran docker stop, then start it again.",
    "crash_loop": "Container keeps restarting. Read the last error in the logs and fix the startup or runtime failure.",
    "app_crash": "App exited with an error. Read the error in the logs and fix it.",
    "scrape_failing": "Prometheus cannot reach the app. Check the container, port and network.",
    "no_failure_detected": "No failure found right now. The alert may have already recovered.",
    "unknown": "Not enough evidence. Check logs and metrics manually.",
}

MEMORY_PHRASES = ["out of memory", "memory leak", "oom-kill", "oom kill", "oom killed"]
UNSUPPORTED = re.compile(r"\b(kubernetes|k8s|evict\w*|pods?|wsgi)\b", re.IGNORECASE)
def is_consistent(category: str, text: str) -> bool:
    """Reject explanations that contradict the rule engine or mention things not in this setup."""
    lower = text.lower()
    if UNSUPPORTED.search(lower):
        return False
    mentions_memory = any(phrase in lower for phrase in MEMORY_PHRASES)
    if category == "memory_leak_oom":
        return mentions_memory
    return not mentions_memory

def parse_status(text: str) -> dict:
    return dict(re.findall(r"(\w+)=(\S+)", text))

def classify(status_text: str, up_text: str) -> dict:
    s = parse_status(status_text)
    running = s.get("running") == "True"
    oom = s.get("oom_killed") == "True"
    exit_code = s.get("exit_code", "")
    restarts = int(s["restart_count"]) if s.get("restart_count", "").isdigit() else 0

    if oom:
        category = "memory_leak_oom"
    elif restarts >= 3:
        category = "crash_loop"
    elif not running and exit_code == "137":
        category = "stopped_externally"
    elif not running and exit_code not in ("", "0"):
        category = "app_crash"
    elif "-> 0" in up_text:
        category = "scrape_failing"
    elif running and "-> 1" in up_text:
        category = "no_failure_detected"
    else:
        category = "unknown"

    return {"category": category, "evidence": status_text, "fix": FIXES[category]}

if __name__ == "__main__":
    cases = [
        ("status=exited running=False exit_code=137 oom_killed=False restart_count=0", "", "stopped_externally"),
        ("status=exited running=False exit_code=137 oom_killed=True restart_count=1", "", "memory_leak_oom"),
        ("status=running running=True exit_code=1 oom_killed=False restart_count=5", "", "crash_loop"),
        ("status=running running=True exit_code=0 oom_killed=False restart_count=0", "{'job': 'flask-app'} -> 1", "no_failure_detected"),
    ]
    for status, up, expected in cases:
        got = classify(status, up)["category"]
        print("OK  " if got == expected else "FAIL", expected, "->", got)

    checks = [
        ("stopped_externally", "Stopped by a Kubernetes eviction.", False),
        ("stopped_externally", "The container was stopped from outside with exit code 137.", True),
        ("stopped_externally", "The app ran out of memory.", False),
        ("memory_leak_oom", "The container ran out of memory.", True),
        ("memory_leak_oom", "The container crashed.", False),
        ("stopped_externally", "It stopped because of the development server warning, use a WSGI server.", False),
    ]
    for category, text, expected in checks:
        got = is_consistent(category, text)
        print("OK  " if got == expected else "FAIL", category, "|", text)