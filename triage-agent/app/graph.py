from __future__ import annotations

import json
import re
from typing import Dict, Any, TypedDict, Annotated

# External deps – OpenAI Python SDK v1+
from openai import OpenAI

# LangGraph – StateGraph API (v0.5+)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  # noqa: F401  (imported for future use)

import settings
import utils

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Instantiate a reusable OpenAI client. The API key is picked up from the
# environment (settings module ensures it is defined), but we pass it
# explicitly for clarity.
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# State definition & node helpers
# ---------------------------------------------------------------------------

# Reducer helpers -----------------------------------------------------------

def _max_float(a: float | None, b: float | None) -> float:
    """Return the maximum of two optional floats treating None as 0.0."""
    return float(max(a or 0.0, b or 0.0))

class IssueState(TypedDict, total=False):
    """Graph state shared between nodes during processing."""

    title: str
    body: str
    number: int
    classification: str  # "bug" | "enhancement" | "question"
    confidence: Annotated[float, _max_float]

# ---------------------------------------------------------------------------
# Node definitions
# ---------------------------------------------------------------------------

def llm_classify(inputs: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Use an LLM to classify the GitHub issue into Bug/Enhancement/Question."""
    title = inputs["title"]
    body = inputs.get("body", "")

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert Python engineer helping triage GitHub issues. "
                "Classify each issue as one of: Bug, Enhancement, Question. "
                "Return a JSON object exactly with keys 'classification' and 'confidence' (0-1)."
            ),
        },
        {
            "role": "user",
            "content": f"Issue title: {title}\n\nIssue body: {body}",
        },
    ]

    # Use the new client-based API (`client.chat.completions.create`) which is
    # the recommended approach for openai>=1.0.0.
    response = client.chat.completions.create(
        model="gpt-4.1",  # Adjust model as needed
        messages=messages,
        temperature=0,
    )
    content = response.choices[0].message.content.strip()

    # Attempt to parse JSON safely
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError(f"LLM response did not contain JSON: {content}")
    data = json.loads(match.group())

    classification: str = str(data["classification"]).lower()
    confidence: float = float(data["confidence"])

    return {
        "classification": classification,
        "confidence": confidence,
    }

def route_on_conf(state: IssueState):
    """Router function used for conditional edges based on confidence."""
    current_conf = float(state.get("confidence", 0.0))
    # High-confidence classification – just apply the predicted label.
    if current_conf >= settings.CONF_THRESHOLD:
        return [
            "apply_label",  # ✔️ add the classification label
        ]

    # Low-confidence path – still apply the classification label, but also add a
    # dedicated low-confidence tag and ask maintainers for review.
    return [
        "apply_label",          # add classification label
        "apply_low_conf_label",  # add (not replace!) low-confidence label
        "comment_for_review",   # ping maintainers
    ]

# ---------------------------------------------------------------------------
# GitHub interaction helpers as graph nodes
# ---------------------------------------------------------------------------

def apply_label(inputs: IssueState, context: Dict[str, Any] | None = None) -> None:
    """Apply the LLM-derived label."""
    utils.apply_label(
        number=inputs["number"],
        label=inputs["classification"],
        owner=settings.REPO_OWNER,
        repo=settings.REPO_NAME,
    )

def comment_for_review(inputs: IssueState, context: Dict[str, Any] | None = None) -> None:
    """Leave a comment asking maintainers to review low-confidence classification."""
    utils.comment_issue(
        number=inputs["number"],
        body="🤖 Low confidence labeling – please review.",
        owner=settings.REPO_OWNER,
        repo=settings.REPO_NAME,
    )

def apply_low_conf_label(inputs: IssueState, context: Dict[str, Any] | None = None) -> None:
    """Tag the issue with a dedicated low-confidence label."""
    # Use POST to add (rather than replace) the low-confidence label so that
    # any existing labels – including the classification label – are
    # preserved.
    utils.apply_label(
        number=inputs["number"],
        label="low_confidence",
        owner=settings.REPO_OWNER,
        repo=settings.REPO_NAME,
    )

# ---------------------------------------------------------------------------
# Graph assembly using StateGraph
# ---------------------------------------------------------------------------

builder = StateGraph(IssueState)

# 1. Node registrations ------------------------------------------------------

builder.add_node("classify", llm_classify)
builder.add_node("apply_label", apply_label)
builder.add_node("comment_for_review", comment_for_review)
builder.add_node("apply_low_conf_label", apply_low_conf_label)

# 2. Graph edges -------------------------------------------------------------

builder.set_entry_point("classify")

# Conditionally branch after classification
builder.add_conditional_edges("classify", route_on_conf)

# Terminate execution after each leaf node
builder.add_edge("apply_label", END)
builder.add_edge("comment_for_review", END)
builder.add_edge("apply_low_conf_label", END)

# Compile into runnable graph
compiled_graph = builder.compile()

# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def process_issue(issue_payload: Dict[str, Any]) -> None:
    """Entry-point for webhook to process a single GitHub issue payload."""
    initial_state = {
        "title": issue_payload.get("title", ""),
        "body": issue_payload.get("body", ""),
        "number": issue_payload.get("number"),
    }

    # Invoke the compiled graph synchronously
    compiled_graph.invoke(initial_state) 