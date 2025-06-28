from __future__ import annotations

import json
import logging
from typing import Any, Dict

import graph

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Lambda Handler -----------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entrypoint compatible with GitHub webhooks via API Gateway.

    If the event is delivered through an API Gateway/Lambda function URL, the
    raw HTTP details live inside the `event` dict. We extract the JSON body and
    forward eligible issue events to `graph.process_issue`.
    """
    try:
        # API Gateway proxy integration wraps the payload in a string under `body`.
        if "body" in event:
            try:
                payload: Dict[str, Any] = json.loads(event["body"] or "{}")
            except json.JSONDecodeError:
                logger.error("Unable to decode JSON body")
                return {"statusCode": 400, "body": "Invalid JSON"}
        else:
            # Direct invocation / test events pass the payload as-is
            payload = event or {}

        # Basic sanity checks for GitHub issue events
        action = payload.get("action")
        issue = payload.get("issue", {})
        if action in {"opened", "edited", "reopened"} and issue.get("state") == "open":
            logger.info("Processing issue #%s", issue.get("number"))
            graph.process_issue(issue)
        else:
            logger.info("Ignoring event action=%s state=%s", action, issue.get("state"))

        return {"statusCode": 200, "body": json.dumps({"msg": "processed"})}

    except Exception as exc:  # pragma: no cover – surface any unexpected errors
        logger.exception("Unhandled exception in Lambda handler: %s", exc)
        return {"statusCode": 500, "body": "Internal Server Error"} 