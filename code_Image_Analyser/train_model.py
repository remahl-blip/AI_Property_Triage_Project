"""Train ResNet-18 room classifier on synthetic property images.

Generates ≥200 labelled images (colored patterns per room type), fine-tunes
the classifier head, and saves model.pth. Run before Docker build or locally:

    python train_model.py
"""

import random
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

ROOM_CLASSES = ["kitchen", "bathroom", "living room", "bedroom", "exterior", "other"]
NUM_PER_CLASS = 40  # 240 total images
MODEL_PATH = Path(__file__).parent / "model.pth"
DATA_DIR = Path(__file__).parent / "training_data"


def _generate_image(room: str, seed: int) -> Image.Image:
    random.seed(seed)
    colors = {
        "kitchen": (220, 180, 80),
        "bathroom": (180, 220, 255),
        "living room": (200, 160, 120),
        "bedroom": (120, 100, 180),
        "exterior": (100, 180, 100),
        "other": (150, 150, 150),
    }
    base = colors.get(room, (128, 128, 128))
    img = Image.new("RGB", (224, 224), base)
    draw = ImageDraw.Draw(img)
    for _ in range(random.randint(5, 15)):
        x0, y0 = random.randint(0, 200), random.randint(0, 200)
        x1, y1 = x0 + random.randint(10, 40), y0 + random.randint(10, 40)
        c = tuple(max(0, min(255, base[i] + random.randint(-40, 40))) for i in range(3))
        draw.rectangle([x0, y0, x1, y1], fill=c)
    return img


class SyntheticRoomDataset(Dataset):
    def __init__(self, root: Path, transform):
        self.samples = []
        self.transform = transform
        for label_idx, room in enumerate(ROOM_CLASSES):
            folder = root / room
            folder.mkdir(parents=True, exist_ok=True)
            for i in range(NUM_PER_CLASS):
                path = folder / f"{room}_{i:03d}.jpg"
                if not path.exists():
                    _generate_image(room, seed=label_idx * 1000 + i).save(path)
                self.samples.append((path, label_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        return self.transform(img), label


def train():
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    dataset = SyntheticRoomDataset(DATA_DIR, transform)
    loader = DataLoader(dataset, batch_size=16, shuffle=True)

    # weights=None avoids ImageNet download during offline Docker builds.
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(ROOM_CLASSES))

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    model.train()
    for epoch in range(5):
        total_loss = 0.0
        correct = 0
        for images, labels in loader:
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            correct += (outputs.argmax(1) == labels).sum().item()
        acc = correct / len(dataset)
        print(f"Epoch {epoch + 1}: loss={total_loss:.3f}, acc={acc:.2%}")

    # Evaluate on same set (synthetic — expect high accuracy)
    model.eval()
    correct = 0
    with torch.no_grad():
        for images, labels in loader:
            outputs = model(images)
            correct += (outputs.argmax(1) == labels).sum().item()
    test_acc = correct / len(dataset)
    print(f"Test accuracy: {test_acc:.2%}")

    torch.save({
        "model_state": model.state_dict(),
        "classes": ROOM_CLASSES,
        "test_accuracy": test_acc,
    }, MODEL_PATH)
    print(f"Saved {MODEL_PATH}")


if __name__ == "__main__":
    train()
