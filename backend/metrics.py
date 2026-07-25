"""Prometheus metrics shared across request and dependency boundaries."""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "foodai_http_requests_total",
    "HTTP requests processed by the API",
    ("method", "route", "status"),
)
HTTP_LATENCY = Histogram(
    "foodai_http_request_duration_seconds",
    "HTTP request latency",
    ("method", "route"),
)
HTTP_IN_PROGRESS = Gauge(
    "foodai_http_requests_in_progress",
    "Requests currently being processed",
    ("method",),
)
EXTERNAL_REQUESTS = Counter(
    "foodai_external_requests_total",
    "Calls to external model services",
    ("service", "outcome"),
)
EXTERNAL_LATENCY = Histogram(
    "foodai_external_request_duration_seconds",
    "External model-service latency",
    ("service",),
)
ANALYSIS_RESULTS = Counter(
    "foodai_analysis_results_total",
    "Food analysis outcomes by inference route",
    ("source", "outcome"),
)
