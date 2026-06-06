import os
from google import genai


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def use_vertex_ai() -> bool:
    return os.getenv("GEMINI_USE_VERTEX_AI", "").strip().lower() in ("1", "true", "yes")


def get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        key = key.replace('"', "").replace("'", "").strip()
        key = "".join(key.split())
    return key


def get_vertex_settings() -> tuple[str, str]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_AI_PROJECT", "")
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_AI_LOCATION", "us-central1")
    return project.strip(), location.strip()


def get_auth_mode() -> str:
    if use_vertex_ai():
        return "vertex_ai"
    if get_api_key():
        return "api_key"
    return "none"


def create_gemini_client():
    if use_vertex_ai():
        project, location = get_vertex_settings()
        if not project:
            raise ValueError(
                "GEMINI_USE_VERTEX_AI is enabled but GOOGLE_CLOUD_PROJECT is not set."
            )
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if credentials_path and not os.path.exists(credentials_path):
            raise ValueError(
                f"GOOGLE_APPLICATION_CREDENTIALS points to missing file: {credentials_path}"
            )
        return genai.Client(vertexai=True, project=project, location=location)

    api_key = get_api_key()
    if api_key:
        return genai.Client(api_key=api_key)
    return None


def create_gemini_client_safe():
    try:
        return create_gemini_client()
    except Exception as exc:
        print(f"[WARN] Failed to initialize Gemini client: {exc}")
        return None


def describe_auth_setup() -> str:
    mode = get_auth_mode()
    if mode == "vertex_ai":
        project, location = get_vertex_settings()
        creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "Application Default Credentials")
        return f"Vertex AI (project={project}, location={location}, credentials={creds})"
    if mode == "api_key":
        key = get_api_key()
        return f"Gemini API key ({key[:6]}...{key[-4:]}, length={len(key)})"
    return "not configured"
