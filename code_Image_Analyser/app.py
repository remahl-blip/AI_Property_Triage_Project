import os

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from image_analysis import analyse_image_bytes, analyse_metadata_only as metadata_analysis

app = FastAPI(title="Image Analyser Service (Layer 3)")

TRIAGE_SERVICE_URL = os.getenv("TRIAGE_SERVICE_URL", "http://property_triage:8003/triage")


class AnalyseJsonRequest(BaseModel):
    image_url: str | None = None
    image_base64: str | None = None
    condition_description: str = ""
    filename: str = "upload.jpg"


def _call_triage(room_type: str, description: str) -> dict:
    triage_payload = {
        "room_type": room_type.replace(" (uncertain)", ""),
        "condition_description": description,
    }
    try:
        triage_response = requests.post(TRIAGE_SERVICE_URL, json=triage_payload, timeout=10)
        if triage_response.status_code == 200:
            return triage_response.json()
        return {"error": f"Property triage error: {triage_response.status_code}"}
    except Exception as exc:
        return {"error": f"Failed to connect to property triage: {exc}"}


def _build_response(filename: str, description: str, analysis: dict, include_triage: bool = True) -> dict:
    keywords_str = " ".join(analysis.get("keywords", []))
    final_description = f"{analysis['detected_issues']} | Keywords: {keywords_str}"
    if description.strip():
        final_description = f"{description.strip()} | {final_description}"

    room_type = analysis["room_type"]
    result = {
        "room_type": room_type,
        "condition_score": analysis["condition_score"],
        "confidence": analysis["confidence"],
        "uncertain": analysis["uncertain"],
        "image_analysis": {
            "processed_file": filename,
            "detected_room": room_type,
            "analysis_notes": analysis["analysis_notes"],
            "condition_description": final_description,
            "pixel_features": analysis.get("pixel_features", {}),
        },
    }
    if include_triage:
        result["triage_decision"] = _call_triage(room_type, final_description)
    return result


async def _load_image_bytes(
    file: UploadFile | None,
    image_url: str | None,
    image_base64: str | None,
) -> tuple[bytes, str]:
    if file is not None:
        content = await file.read()
        return content, file.filename or "upload.jpg"

    if image_base64:
        import base64

        return base64.b64decode(image_base64), "upload.jpg"

    if image_url:
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        name = image_url.rstrip("/").split("/")[-1] or "remote.jpg"
        return response.content, name

    raise ValueError("Provide file upload, image_url, or image_base64")


@app.post("/analyse")
async def analyse_image(request: Request):
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        payload = AnalyseJsonRequest(**body)
        description = payload.condition_description
        filename = payload.filename or "upload.jpg"
        if payload.image_url or payload.image_base64:
            image_bytes, filename = await _load_image_bytes(
                None, payload.image_url, payload.image_base64
            )
            if payload.filename:
                filename = payload.filename
            analysis = analyse_image_bytes(image_bytes, filename, description)
        else:
            analysis = metadata_analysis(filename, description)
    else:
        form = await request.form()
        upload = form.get("file")
        description = str(form.get("condition_description") or "")
        if upload is None:
            raise HTTPException(status_code=422, detail="Multipart request requires 'file' field")
        image_bytes = await upload.read()
        filename = upload.filename or "inspection.jpg"
        analysis = analyse_image_bytes(image_bytes, filename, description)
    return _build_response(filename, description, analysis)


@app.post("/analyse/metadata")
async def analyse_upload_metadata(
    file: UploadFile = File(None),
    condition_description: str = Form(default=""),
    image_url: str = Form(default=""),
):
    """Backward-compatible endpoint for simple multipart uploads."""
    image_bytes, filename = await _load_image_bytes(file, image_url or None, None)
    analysis = analyse_image_bytes(image_bytes, filename, condition_description)
    return _build_response(filename, condition_description, analysis, include_triage=True)


@app.get("/health")
def health():
    return {"status": "ok", "layer": 3, "service": "image_analyser"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
