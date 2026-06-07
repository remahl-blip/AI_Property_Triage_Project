"""Client utilities for submitting property listings to n8n."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


class OrchestrationError(Exception):
    """Raised when the WebUI cannot submit a listing to n8n."""


@dataclass(frozen=True)
class UploadedImage:
    filename: str
    content_type: str
    data: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def build_property_submission_payload(
    *,
    description: str,
    agent_name: str,
    images: list[UploadedImage],
) -> dict[str, Any]:
    """Build the JSON body expected by the n8n webhook."""

    encoded_images = [
        {
            "filename": image.filename,
            "content_type": image.content_type,
            "size_bytes": image.size_bytes,
            "data_base64": base64.b64encode(image.data).decode("ascii"),
        }
        for image in images
    ]

    return {
        "source": "streamlit-webui",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "listing": {
            "description": description.strip(),
            "agent_name": agent_name.strip(),
            "images": encoded_images,
            "image_urls": [],
        },
        "service_routing": {
            "image_analyser": {
                "status": "connected",
                "endpoint": "http://image_analyser:8002/analyse",
            },
            "property_triage": {
                "status": "connected",
                "endpoint": "http://property_triage:8003/triage",
                "history_endpoint": "http://property_triage:8003/history",
            },
            "rag_service": {
                "status": "pending_integration",
                "endpoint": "POST /query",
            },
            "guardrails": {
                "status": "pending_integration",
                "input_endpoint": "POST /check/input",
                "output_endpoint": "POST /check/output",
            },
            "langgraph_agent": {
                "status": "pending_integration",
                "endpoint": "POST /agent/run",
            },
        },
    }


def submit_to_n8n(
    *,
    webhook_url: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    """Send the property submission payload to n8n and return a normalized result."""

    if not webhook_url:
        raise OrchestrationError("N8N_WEBHOOK_URL is not configured. Create .env from .env.example.")

    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise OrchestrationError("n8n request timed out. Check that the workflow is running.") from exc
    except requests.ConnectionError as exc:
        raise OrchestrationError("Could not connect to n8n. Check N8N_WEBHOOK_URL and network access.") from exc
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        response_text = exc.response.text if exc.response is not None else ""
        raise OrchestrationError(f"n8n returned HTTP {status_code}: {response_text}") from exc
    except requests.RequestException as exc:
        raise OrchestrationError(f"Unexpected n8n request error: {exc}") from exc

    if not response.content:
        return {
            "status": "success",
            "message": "n8n accepted the submission but returned an empty response.",
            "data": None,
        }

    try:
        return {
            "status": "success",
            "message": "n8n returned a JSON response.",
            "data": response.json(),
        }
    except ValueError:
        return {
            "status": "success",
            "message": "n8n returned a non-JSON response.",
            "data": response.text,
        }
