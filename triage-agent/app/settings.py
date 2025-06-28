import os

# GitHub and OpenAI credentials
GH_TOKEN: str | None = os.getenv("GH_TOKEN")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# Repository information
REPO_OWNER: str | None = os.getenv("REPO_OWNER")  # e.g. "octocat"
REPO_NAME: str | None = os.getenv("REPO_NAME")    # e.g. "hello-world"

# Classification parameters
CONF_THRESHOLD: float = float(os.getenv("CONF_THRESHOLD", "0.8"))

# Optional vector-store / OpenSearch configuration
OPENSEARCH_HOST: str | None = os.getenv("OPENSEARCH_HOST")
OPENSEARCH_USER: str | None = os.getenv("OPENSEARCH_USER")
OPENSEARCH_PASS: str | None = os.getenv("OPENSEARCH_PASS")
VECTOR_INDEX: str = os.getenv("VECTOR_INDEX", "issue-edge-cases")

# Convenience helpers for required configuration
REQUIRED_VARS = [
    ("GH_TOKEN", GH_TOKEN),
    ("OPENAI_API_KEY", OPENAI_API_KEY),
    ("REPO_OWNER", REPO_OWNER),
    ("REPO_NAME", REPO_NAME),
]

missing = [name for name, value in REQUIRED_VARS if not value]
if missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing)}"
    ) 