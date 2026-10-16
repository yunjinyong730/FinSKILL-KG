from __future__ import annotations

from pathlib import Path

import joblib


class TrainedSkillRouter:
    def __init__(self, model_path: str | Path):
        payload = joblib.load(model_path)
        self.vectorizer = payload["vectorizer"]
        self.classifier = payload["classifier"]
        self.classes = tuple(payload["classes"])

    def predict(self, question: str) -> str:
        features = self.vectorizer.transform([question])
        return str(self.classifier.predict(features)[0])

    def predict_with_confidence(self, question: str) -> tuple[str, float]:
        features = self.vectorizer.transform([question])
        probabilities = self.classifier.predict_proba(features)[0]
        index = int(probabilities.argmax())
        return str(self.classifier.classes_[index]), float(probabilities[index])
