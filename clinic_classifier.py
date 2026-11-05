"""Pure-Python version of the clinic question classifier.

It preserves the C++ classifier's inference pipeline:
1. Tokenize the question using the same basic normalization.
2. Average pretrained word vectors for known words.
3. L2-normalize the mean sentence vector.
4. Apply the trained 3-class softmax weights.
5. Apply the same emergency phrase override.

No C/C++ compiler or executable is required.
"""

from __future__ import annotations

from array import array
import math
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
EMBEDDING_FILE = BASE_DIR / "Embeddings.vec"
WEIGHTS_FILE = BASE_DIR / "classifier_weights.txt"
LABELS = ("ROUTINE", "SENSITIVE", "UNSUPPORTED")
CLASS_COUNT = len(LABELS)
TOKEN_RE = re.compile(r"[^a-zA-Z0-9']+")
EMERGENCY_PHRASES = (
    "severe chest pain",
    "not breathing",
    "turned blue",
    "difficulty breathing",
    "pregnant and bleeding",
    "want to end my life",
    "kill myself",
    "immediate danger",
)


class ClinicClassifier:
    """Loads the embedding and trained classifier files once per process."""

    def __init__(self, embedding_path: Path = EMBEDDING_FILE,
                 weights_path: Path = WEIGHTS_FILE) -> None:
        self.embedding_path = Path(embedding_path)
        self.weights_path = Path(weights_path)
        self.vocab_size = 0
        self.dimension = 0
        self.word_offsets: dict[str, int] = {}
        # A packed C double array avoids the very high memory overhead of
        # millions of individual Python float objects.
        self.vector_values = array("d")
        self.biases: list[float] = []
        self.weights: list[list[float]] = []
        self._load_embeddings()
        self._load_weights()

    @staticmethod
    def normalize(text: str) -> str:
        text = text.lower()
        return TOKEN_RE.sub(" ", text)

    @classmethod
    def tokenize(cls, text: str) -> list[str]:
        return cls.normalize(text).split()

    def _load_embeddings(self) -> None:
        if not self.embedding_path.is_file():
            raise FileNotFoundError(f"Embedding file not found: {self.embedding_path}")

        with self.embedding_path.open("r", encoding="utf-8", errors="replace") as file:
            header = file.readline().split()
            if len(header) != 2:
                raise ValueError("Invalid Embeddings.vec header; expected vocabulary_size dimensions")
            self.vocab_size, self.dimension = map(int, header)
            if self.vocab_size <= 0 or self.dimension <= 0:
                raise ValueError("Embedding vocabulary size and dimensions must be positive")

            loaded = 0
            for line_number, line in enumerate(file, start=2):
                parts = line.split()
                if not parts:
                    continue
                word = parts[0]
                values = parts[1:]
                if len(values) != self.dimension:
                    raise ValueError(
                        f"Invalid embedding row at line {line_number}: "
                        f"expected {self.dimension} values, got {len(values)}"
                    )
                if word in self.word_offsets:
                    continue
                self.word_offsets[word] = len(self.vector_values)
                try:
                    self.vector_values.extend(float(value) for value in values)
                except ValueError as exc:
                    raise ValueError(f"Non-numeric embedding value at line {line_number}") from exc
                loaded += 1

        if loaded == 0:
            raise ValueError("Embedding file contains no vectors")

    def _load_weights(self) -> None:
        if not self.weights_path.is_file():
            raise FileNotFoundError(f"Classifier weights file not found: {self.weights_path}")

        # Ignore trailing comment lines; the C++ loader also stops after the
        # expected parameters and therefore ignores these annotations.
        weight_text = "\n".join(
            line.split("#", 1)[0] for line in self.weights_path.read_text(encoding="utf-8").splitlines()
        )
        values = weight_text.split()
        if len(values) < 2:
            raise ValueError("Classifier weight file is incomplete")
        classes, model_dimension = int(values[0]), int(values[1])
        if classes != CLASS_COUNT or model_dimension != self.dimension:
            raise ValueError(
                "Classifier weight dimensions do not match embeddings: "
                f"expected {CLASS_COUNT} classes and {self.dimension} dimensions, "
                f"found {classes} classes and {model_dimension} dimensions"
            )

        expected = 2 + CLASS_COUNT * (self.dimension + 1)
        if len(values) != expected:
            raise ValueError(
                f"Classifier weights contain {len(values) - 2} parameters; "
                f"expected {CLASS_COUNT * (self.dimension + 1)}"
            )

        cursor = 2
        self.biases = []
        self.weights = []
        for _class_index in range(CLASS_COUNT):
            self.biases.append(float(values[cursor]))
            cursor += 1
            row = [float(value) for value in values[cursor:cursor + self.dimension]]
            cursor += self.dimension
            self.weights.append(row)

    def _emergency_override(self, question: str) -> bool:
        normalized = " " + self.normalize(question).strip() + " "
        return any(
            " " + self.normalize(phrase).strip() + " " in normalized
            for phrase in EMERGENCY_PHRASES
        )

    def classify(self, question: str) -> dict[str, Any]:
        tokens = self.tokenize(question)
        total = len(tokens)
        known_tokens = [token for token in tokens if token in self.word_offsets]
        known = len(known_tokens)
        emergency = self._emergency_override(question)

        # This matches the C++ OOV behavior: do not invent a model prediction
        # when none of the query's words exist in the embedding vocabulary.
        if known == 0:
            category = "SENSITIVE" if emergency else "UNSUPPORTED"
            return {
                "category": category,
                "score": 0.0,
                "margin": 0.0,
                "matched": "",
                "answer": "",
                "retrieval": "WEAK",
                "safety": "EMERGENCY" if emergency else "",
                "coverage": {"known": known, "total": total},
                "class_scores": {label: 0.0 for label in LABELS},
            }

        # Average the known word vectors, matching the C++ sentence-vector logic.
        sentence = [0.0] * self.dimension
        for token in known_tokens:
            offset = self.word_offsets[token]
            for index in range(self.dimension):
                sentence[index] += self.vector_values[offset + index]
        inverse_count = 1.0 / known
        for index in range(self.dimension):
            sentence[index] *= inverse_count

        # L2 normalize the mean vector.
        norm = math.sqrt(sum(value * value for value in sentence))
        if norm > 1e-12:
            inverse_norm = 1.0 / norm
            sentence = [value * inverse_norm for value in sentence]

        logits = []
        for class_index in range(CLASS_COUNT):
            score = self.biases[class_index]
            row = self.weights[class_index]
            for index in range(self.dimension):
                score += row[index] * sentence[index]
            logits.append(score)

        # Numerically stable softmax.
        max_logit = max(logits)
        exponentials = [math.exp(value - max_logit) for value in logits]
        exp_sum = sum(exponentials)
        probabilities = [value / exp_sum for value in exponentials]
        predicted_index = max(range(CLASS_COUNT), key=probabilities.__getitem__)
        category = LABELS[predicted_index]
        if emergency:
            category = "SENSITIVE"

        return {
            "category": category,
            "score": probabilities[predicted_index],
            # The original runtime emitted 0 for this field; preserve its API.
            "margin": 0.0,
            "matched": "",
            "answer": "",
            "retrieval": "WEAK",
            "safety": "EMERGENCY" if emergency else ("SENSITIVE" if category == "SENSITIVE" else ""),
            "coverage": {"known": known, "total": total},
            "class_scores": {
                label: probabilities[index] for index, label in enumerate(LABELS)
            },
        }


_classifier: ClinicClassifier | None = None


def get_classifier() -> ClinicClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ClinicClassifier()
    return _classifier


def classify_question(question: str) -> dict[str, Any]:
    return get_classifier().classify(question)
