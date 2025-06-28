# Standard library
import os
import sys
import importlib
import json
from pathlib import Path

# Third-party
from dotenv import load_dotenv, find_dotenv

# Ensure the app package directory is on PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent / "app"
sys.path.insert(0, str(BASE_DIR))

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------

# Load environment variables from a .env file located in the project root (if present)
_dotenv_path = find_dotenv()
if _dotenv_path:
    load_dotenv(_dotenv_path)

# Fail fast if critical variables are still missing – this surfaces config issues early.
_required = [
    "OPENAI_API_KEY",
    "GH_TOKEN",
    "REPO_OWNER",
    "REPO_NAME",
]

missing = [var for var in _required if not os.getenv(var)]
if missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing)}"
    )

# ---------------------------------------------------------------------------
# Stub GitHub API calls (to avoid network requests during test run)
# ---------------------------------------------------------------------------

import utils  # type: ignore  # noqa: E402


def _no_op_request(*_args, **_kwargs):
    return {}


utils._github_request = _no_op_request  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Import the Lambda-style handler and invoke it with a sample payload
# ---------------------------------------------------------------------------

handler_module = importlib.import_module("lambda_handler")

event_payload = {
    "action": "opened",
    "issue": {
        "number": 101,
        "title": "Sample issue title",
        "body": "Steps to reproduce the problem...",
        "state": "open",
    },
}

result = handler_module.handler(event_payload, context=None)
print(json.dumps(result, indent=2)) 