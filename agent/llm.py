import requests

OLLAMA_URL = "http://host.docker.internal:11434"
MODEL = "qwen2.5:7b"

def ask_llm(prompt: str) -> str:
    """Send a single prompt to Ollama and return the text reply."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=300,
        )
        return response.json()["message"]["content"]
    except Exception as error:
        return f"llm call failed: {error}"