import logging
import time
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency in seconds", ["route"])

@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_metrics(response):
    if request.path != "/metrics":
        REQUESTS.labels(request.path, response.status_code).inc()
        LATENCY.labels(request.path).observe(time.time() - request.start_time)
    return response

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/health")
def health():
    return jsonify(status="ok")

@app.route("/work")
def work():
    start = time.time()
    total = sum(i * i for i in range(100000))
    duration = round(time.time() - start, 3)
    app.logger.info("work completed in %s seconds", duration)
    return jsonify(result=total, duration=duration)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)