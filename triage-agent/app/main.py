from __future__ import annotations

import hmac
import hashlib
import os
import logging
import sys
import time

# Third-party
from flask import Flask, request, jsonify, abort, g
from contextlib import suppress

# graph will be imported later after env variables are loaded

# ---------------------------------------------------------------------------
# Logging – ensure everything (Flask, ngrok, our code) streams to stdout
# ---------------------------------------------------------------------------

# Reset and configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Ensure Flask/werkzeug request logs are visible
logging.getLogger("werkzeug").setLevel(logging.INFO)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Webhook secret (new env var: GH_WEBHOOKSECRET). Fallback to legacy var.
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = os.getenv("GH_WEBHOOKSECRET") or os.getenv("GITHUB_WEBHOOK_SECRET")

# Load environment variables from a .env file if present when running locally.
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    from pathlib import Path

    _dotenv_path = Path(__file__).resolve().parents[2] / ".env"
    if _dotenv_path.is_file():
        load_dotenv(_dotenv_path)
except ModuleNotFoundError:
    # python-dotenv is optional in production containers; ignore if missing
    pass

# Now that environment variables are loaded, we can safely import the graph module.
import graph  # noqa: E402

def _verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256 header when a secret is configured."""
    if not WEBHOOK_SECRET:
        return True  # Not configured – skip validation

    if signature_header is None or not signature_header.startswith("sha256="):
        return False

    signature = signature_header.split("=", 1)[1]
    mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    return hmac.compare_digest(signature, expected)


@app.route("/webhook", methods=["POST"])
def github_webhook():
    # Signature verification
    if not _verify_signature(request.data, request.headers.get("X-Hub-Signature-256")):
        logger.warning("Invalid webhook signature")
        abort(401, "Invalid signature")

    event = request.headers.get("X-GitHub-Event")
    if event != "issues":
        return jsonify({"msg": "ignored – not an issue event"}), 200

    payload = request.json or {}
    action = payload.get("action")
    if action not in {"opened", "edited", "reopened"}:
        return jsonify({"msg": "ignored – action not relevant"}), 200

    issue_data = payload.get("issue", {})
    if issue_data.get("state") != "open":
        return jsonify({"msg": "ignored – issue not open"}), 200

    logger.info("Processing issue #%s", issue_data.get("number"))
    graph.process_issue(issue_data)

    return jsonify({"msg": "processed"}), 200


@app.before_request
def _set_start_time():
    g._start_time = time.time()


@app.after_request
def _log_response(resp):
    duration = (time.time() - g.get("_start_time", time.time())) * 1000
    logger.info("%s %s -> %s (%.1f ms)", request.method, request.path, resp.status_code, duration)
    return resp


# ---------------------------------------------------------------------------
# Root endpoint – handles GitHub's initial webhook ping
# ---------------------------------------------------------------------------


@app.route("/", methods=["POST", "GET"])
def root_healthcheck():
    """Respond to GitHub's ping event or simple health checks.

    According to GitHub Webhook docs, when a webhook is created GitHub sends a
    `ping` event (header `X-GitHub-Event: ping`) to the *exact* payload URL to
    verify it (see docs.github.com/en/developers/webhooks-and-events/webhooks/about-webhooks#ping-event).
    Returning any 2xx response marks the endpoint as valid.
    """
    if request.headers.get("X-GitHub-Event") == "ping":
        logger.info("Received GitHub ping event – responding with pong")
        return jsonify({"msg": "pong"}), 200

    # Fallback – basic health response
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))

    # ------------------------------------------------------------------
    # Optional: start an ngrok tunnel for local webhook testing
    # ------------------------------------------------------------------

    if os.getenv("ENABLE_NGROK", "false").lower() == "true":
        try:
            import ngrok  # type: ignore

            # Establish a public ingress to the local Flask server.
            listener = ngrok.forward(port, authtoken_from_env=True)
            public_url = listener.url()
            message = (
                f"NGROK tunnel established: {public_url} -> http://localhost:{port}\n"
                f"Set your GitHub webhook URL to: {public_url}/webhook"
            )
            print(message, flush=True)
            logger.info(message)
        except ModuleNotFoundError as exc:  # pragma: no cover
            logger.error("ENABLE_NGROK is set but the 'ngrok' package is not installed: %s", exc)
        except Exception as exc:  # pragma: no cover – surface but don't crash
            logger.exception("Failed to start ngrok tunnel: %s", exc)

    # Start Flask app
    app.run(host="0.0.0.0", port=port) 