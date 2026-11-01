
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
MAX_REQUEST_BYTES = 83886080  # limits.max_request_bytes of your configuration (80 MiB, D77)
TIMEOUT = 120  # seconds; the server may count the pages of large PDFs for up to 60 s


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.headers, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, error.headers, json.loads(error.read())


path = sys.argv[1] if len(sys.argv) > 1 else "my_cases/example.json"
with open(path, encoding="utf-8") as handle:
    body = json.load(handle)
body["request_id"] = f"dev-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1000000}"
size = len(json.dumps(body).encode("utf-8"))
if size > MAX_REQUEST_BYTES:
    print("rejected 413 REQUEST_TOO_LARGE", f"(body {size} bytes > {MAX_REQUEST_BYTES}; not sent)")
    sys.exit(1)
try:
    status, headers, job = call("POST", "/v1/assessments", body)
except OSError as error:
    reason = getattr(error, "reason", error)
    if isinstance(reason, ConnectionRefusedError):
        print("cannot reach", BASE, "- is the server running?")
    elif isinstance(reason, (BrokenPipeError, ConnectionResetError)):
        # the server answers 413 before it reads a body over its limit and closes the connection
        print("rejected 413 REQUEST_TOO_LARGE", f"(the server closed the connection while {size}",
              f"bytes were sent: {reason}; its limits.max_request_bytes is lower)")
    elif isinstance(reason, TimeoutError):
        print("no answer from", BASE, f"within {TIMEOUT} s - is the server stuck? see its log")
    else:
        print("connection to", BASE, "failed:", reason)
    sys.exit(1)
if status != 202:
    error = job.get("error", {})
    print("rejected", status, error.get("code"), json.dumps(error.get("field_errors", [])))
    sys.exit(1)
while job["job_status"] != "finished":
    time.sleep(0.5)
    _, _, job = call("GET", headers["Location"])
result, diagnostics = job["result"], job["diagnostics"]
print("request_id    ", body["request_id"])
print("result_origin ", job["result_origin"])
print("status        ", result["assessment_status"], "| predicted_trl", result["predicted_trl"],
      "| error_code", result["error_code"])
print("timings_ms    ", diagnostics.get("timings_ms"))
if "failure" in diagnostics:
    print("failure       ", diagnostics["failure"]["message"])
for issue in diagnostics.get("output_issues", []):
    print("output issue  ", issue["path"], issue["rule"])
print("module logs   ", f"server_data/jobs/{job['assessment_id']}/stderr.log")
