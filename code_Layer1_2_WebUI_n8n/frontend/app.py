"""Streamlit WebUI for the AI-powered property triage system."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings
from orchestration.n8n_client import (
    OrchestrationError,
    UploadedImage,
    build_property_submission_payload,
    submit_to_n8n,
)


REAL_ESTATE_ASSISTANT_PROMPT = """
You are a real estate assistant for listing agents.
Answer property-market and listing-preparation questions clearly and factually.
Do not invent prices, legal claims, certifications, or guarantees.
If the user asks for legal, financial, medical, or unrelated advice, politely refuse and redirect to real estate listing support.
""".strip()


def ask_ollama(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: int,
) -> str:
    """Send a chat message to local Ollama."""

    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [{"role": "system", "content": REAL_ESTATE_ASSISTANT_PROMPT}, *messages],
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.Timeout:
        return "Ollama timed out. Check that the local model is running."
    except requests.ConnectionError:
        return "Could not connect to Ollama. Start it locally and verify OLLAMA_BASE_URL."
    except requests.HTTPError as exc:
        return f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
    except requests.RequestException as exc:
        return f"Unexpected Ollama error: {exc}"

    try:
        data: dict[str, Any] = response.json()
    except ValueError:
        return "Ollama returned a non-JSON response."

    return data.get("message", {}).get("content", "Ollama returned no assistant message.")


def render_assistant(settings) -> None:
    st.subheader("Conversational Assistant")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about property listing preparation")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Contacting local Ollama..."):
                answer = ask_ollama(
                    base_url=settings.ollama_base_url,
                    model=settings.ollama_model,
                    messages=st.session_state.chat_messages,
                    timeout_seconds=settings.request_timeout_seconds,
                )
            st.markdown(answer)

        st.session_state.chat_messages.append({"role": "assistant", "content": answer})


def render_submission_form(settings) -> None:
    st.subheader("Property Submission")

    with st.form("property_submission_form", clear_on_submit=False):
        agent_name = st.text_input("Listing agent name")
        description = st.text_area(
            "Listing description",
            height=220,
            placeholder="Describe the property type, location, price, rooms, condition, and key features.",
        )
        uploaded_files = st.file_uploader(
            "Upload property images",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )

        submitted = st.form_submit_button("Submit to n8n")

    if not submitted:
        return

    if not agent_name.strip():
        st.error("Agent name is required.")
        return

    if not description.strip():
        st.error("Listing description is required.")
        return

    images = [
        UploadedImage(
            filename=file.name,
            content_type=file.type or "application/octet-stream",
            data=file.getvalue(),
        )
        for file in uploaded_files
    ]

    payload = build_property_submission_payload(
        description=description,
        agent_name=agent_name,
        images=images,
    )

    with st.expander("Payload preview"):
        preview_payload = payload.copy()
        preview_payload["listing"] = {
            **payload["listing"],
            "images": [
                {
                    "filename": image["filename"],
                    "content_type": image["content_type"],
                    "size_bytes": image["size_bytes"],
                    "data_base64": "<omitted from preview>",
                }
                for image in payload["listing"]["images"]
            ],
        }
        st.json(preview_payload)

    with st.spinner("Submitting listing to n8n..."):
        try:
            result = submit_to_n8n(
                webhook_url=settings.n8n_webhook_url,
                payload=payload,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except OrchestrationError as exc:
            st.error(str(exc))
            return

    st.success(result["message"])
    st.subheader("Final Response from n8n")

    if isinstance(result["data"], (dict, list)):
        st.json(result["data"])
    elif result["data"] is None:
        st.info("No response body returned.")
    else:
        st.markdown(str(result["data"]))


def main() -> None:
    settings = get_settings()

    st.set_page_config(
        page_title="Property Triage WebUI",
        page_icon="house",
        layout="wide",
    )

    st.title("AI-Powered Property Triage")

    assistant_tab, submission_tab = st.tabs(["Assistant", "Submit Listing"])

    with assistant_tab:
        render_assistant(settings)

    with submission_tab:
        render_submission_form(settings)


if __name__ == "__main__":
    main()
