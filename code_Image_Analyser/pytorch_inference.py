"""PyTorch ResNet-18 inference for room classification + condition scoring."""

import io
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

MODEL_PATH = Path(__file__).parent / "model.pth"
CONFIDENCE_THRESHOLD = 0.55

_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

_model = None
_classes = None


def _load_model():
    global _model, _classes
    if _model is not None:
        return
    if not MODEL_PATH.exists():
        return
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    _classes = checkpoint.get("classes", [])
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(_classes))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    _model = model


def predict_room(image_bytes: bytes) -> dict | None:
    _load_model()
    if _model is None or not _classes:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    tensor = _transform(img).unsqueeze(0)
    with torch.no_grad():
        logits = _model(tensor)
        probs = torch.softmax(logits, dim=1)[0]
        conf, idx = probs.max(dim=0)
    room = _classes[int(idx)]
    confidence = float(conf)
    uncertain = confidence < CONFIDENCE_THRESHOLD
    # Map confidence to condition score 1-5 (higher conf + neutral brightness → better)
    condition_score = max(1, min(5, round(2 + confidence * 3)))
    return {
        "room_type": f"{room} (uncertain)" if uncertain else room,
        "condition_score": condition_score,
        "confidence": round(confidence, 3),
        "uncertain": uncertain,
        "model": "resnet18",
    }
