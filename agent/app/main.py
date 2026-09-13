"""Minimal FastAPI host for the agent service.

This keeps the backend entrypoint thin while the rest of the agent is built out.
"""

from fastapi import FastAPI


app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
	"""Return a simple liveness response for the agent process."""
	return {"status": "ok"}
