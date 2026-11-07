import re
from pathlib import Path
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
LABELS = ("ROUTINE", "SENSITIVE", "UNSUPPORTED")
TOKEN_RE = re.compile(r"[^a-zA-Z0-9']+")


class ClinicClassifier:
    def __init__(self):
        self.word_offsets = {}
        self._load_embeddings()
        self._load_weights()

    @staticmethod
    def normalize(text):
        return TOKEN_RE.sub(" ", text.lower())

    @classmethod
    def tokenize(cls, text):
        return cls.normalize(text).split()

    def _load_embeddings(self):
        with (BASE_DIR / "Embeddings.vec").open(encoding="utf-8") as file:
            self.vocab_size, self.dimension = map(int, file.readline().split())
            self.embeddings = np.empty(
                (self.vocab_size, self.dimension), dtype=np.float64
            )

            for row, line in enumerate(file):
                parts = line.split()
                if parts:
                    self.word_offsets[parts[0]] = row
                    self.embeddings[row] = parts[1:]

    def _load_weights(self):
        text = "\n".join(
            line.split("#", 1)[0]
            for line in (BASE_DIR / "classifier_weights.txt").read_text().splitlines()
        )
        values = np.fromstring(text, sep=" ")
        parameters = values[2:].reshape(len(LABELS), self.dimension + 1)
        self.biases = parameters[:, 0]
        self.weights = parameters[:, 1:]

    def classify(self, question):
        tokens = self.tokenize(question)
        known = [self.word_offsets[word] for word in tokens if word in self.word_offsets]
        if not known:
            category = "UNSUPPORTED"
            return {
                "category": category,
                "score": 0.0,
                "margin": 0.0,
                "matched": "",
                "answer": "",
                "retrieval": "WEAK",
                "safety": "",
                "coverage": {"known": 0, "total": len(tokens)},
                "class_scores": dict.fromkeys(LABELS, 0.0),
            }

        sentence = self.embeddings[known].mean(axis=0)
        norm = np.linalg.norm(sentence)
        if norm > 1e-12:
            sentence /= norm

        logits = self.weights @ sentence + self.biases
        probabilities = np.exp(logits - logits.max())
        probabilities /= probabilities.sum()

        predicted = int(probabilities.argmax())
        category = LABELS[predicted]

        return {
            "category": category,
            "score": float(probabilities[predicted]),
            "margin": 0.0,
            "matched": "",
            "answer": "",
            "retrieval": "WEAK",
            "safety": "SENSITIVE" if category == "SENSITIVE" else "",
            "coverage": {"known": len(known), "total": len(tokens)},
            "class_scores": {
                label: float(probabilities[i])
                for i, label in enumerate(LABELS)
            },
        }


_classifier = None


def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = ClinicClassifier()
    return _classifier


def classify_question(question):
    return get_classifier().classify(question)
