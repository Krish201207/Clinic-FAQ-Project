"""
Pure-Python replacement for train_classifier.cpp.

Matches the C++ classifier-training logic:
- loads Embeddings.vec
- reads LABEL<TAB>question from classification_data.txt
- averages known word vectors, then L2-normalizes the sentence vector
- skips examples whose sentence vector is zero
- 3-class softmax: ROUTINE=0, SENSITIVE=1, UNSUPPORTED=2
- 100 epochs, shuffled examples, learning rate 0.05, L2=0.0001
- online/one-example-at-a-time gradient updates
- writes classifier_weights.txt in the exact format read by clinic_classifier.py

Run: python train_classifier.py
Inputs: Embeddings.vec, classification_data.txt
Output: classifier_weights.txt
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EMBEDDING_FILE = BASE_DIR / "Embeddings.vec"
TRAINING_FILE = BASE_DIR / "classification_data.txt"
OUTPUT_FILE = BASE_DIR / "classifier_weights.txt"

LABELS = {
    "ROUTINE": 0,
    "SENSITIVE": 1,
    "UNSUPPORTED": 2,
}
CLASS_COUNT = 3
EPOCHS = 100
LEARNING_RATE = 0.05
L2 = 0.0001
SEED = None  # Set an integer (e.g. 42) for repeatable training runs.

TOKEN_RE = re.compile(r"[^a-zA-Z0-9']+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.sub(" ", text.lower()).split()


def load_embeddings(path: Path) -> tuple[dict[str, list[float]], int]:
    if not path.is_file():
        raise FileNotFoundError(f"Cannot open {path.name}")

    embeddings: dict[str, list[float]] = {}
    with path.open("r", encoding="utf-8", errors="replace") as file:
        header = file.readline().split()
        if len(header) != 2:
            raise ValueError("Invalid embedding header; expected vocabulary_size dimensions.")

        vocabulary_size, dimension = map(int, header)
        if vocabulary_size <= 0 or dimension <= 0:
            raise ValueError("Invalid embedding vocabulary size or dimension.")

        for line_number in range(2, vocabulary_size + 2):
            line = file.readline()
            if not line:
                break
            parts = line.split()
            if not parts:
                continue
            word, values = parts[0], parts[1:]
            if len(values) != dimension:
                raise ValueError(
                    f"Invalid embedding row at line {line_number}: "
                    f"expected {dimension} values, found {len(values)}."
                )
            embeddings.setdefault(word, [float(value) for value in values])

    if not embeddings:
        raise ValueError("No embeddings were loaded.")
    return embeddings, dimension


def make_sentence_vector(
    text: str,
    embeddings: dict[str, list[float]],
    dimension: int,
) -> list[float]:
    result = [0.0] * dimension
    known = 0

    for word in tokenize(text):
        vector = embeddings.get(word)
        if vector is None:
            continue
        for index in range(dimension):
            result[index] += vector[index]
        known += 1

    if known == 0:
        return result

    result = [value / known for value in result]
    norm = math.sqrt(sum(value * value for value in result))

    if norm > 1e-12:
        result = [value / norm for value in result]

    return result


def softmax(logits: list[float]) -> list[float]:
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def load_training_examples(
    path: Path,
    embeddings: dict[str, list[float]],
    dimension: int,
) -> list[tuple[list[float], int]]:
    if not path.is_file():
        raise FileNotFoundError(f"Cannot open {path.name}")

    examples: list[tuple[list[float], int]] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue

            if "\t" not in line:
                raise ValueError(
                    f"Line {line_number}: expected LABEL, a tab, and question text."
                )

            label_text, question = line.split("\t", 1)
            label_text = label_text.strip()

            if label_text not in LABELS:
                raise ValueError(f"Line {line_number}: unknown label {label_text!r}.")

            features = make_sentence_vector(question, embeddings, dimension)
            squared_norm = sum(value * value for value in features)

            # Same as the C++ trainer: ignore all-OOV/zero-vector examples.
            if squared_norm > 1e-20:
                examples.append((features, LABELS[label_text]))

    if not examples:
        raise ValueError("No usable training examples were found.")
    return examples


def main() -> None:
    rng = random.Random(SEED)
    embeddings, dimension = load_embeddings(EMBEDDING_FILE)
    examples = load_training_examples(TRAINING_FILE, embeddings, dimension)

    weights = [[0.0] * dimension for _ in range(CLASS_COUNT)]
    biases = [0.0] * CLASS_COUNT

    print(f"Loaded embeddings: {len(embeddings)}")
    print(f"Embedding dimensions: {dimension}")
    print(f"Training examples: {len(examples)}")
    print(f"Classes: {', '.join(LABELS)}")

    for epoch in range(EPOCHS):
        rng.shuffle(examples)
        total_loss = 0.0

        for features, correct_label in examples:
            logits = [
                biases[class_index]
                + sum(
                    weights[class_index][j] * features[j]
                    for j in range(dimension)
                )
                for class_index in range(CLASS_COUNT)
            ]

            probabilities = softmax(logits)
            total_loss -= math.log(max(probabilities[correct_label], 1e-12))

            # Online gradient descent, matching the C++ update order.
            for class_index in range(CLASS_COUNT):
                error = probabilities[class_index] - (
                    1.0 if class_index == correct_label else 0.0
                )
                biases[class_index] -= LEARNING_RATE * error

                for j in range(dimension):
                    gradient = error * features[j] + L2 * weights[class_index][j]
                    weights[class_index][j] -= LEARNING_RATE * gradient

        print(
            f"Epoch {epoch + 1}/{EPOCHS} "
            f"Loss: {total_loss / len(examples):.6f}"
        )

    # Exact layout expected by clinic_classifier.py:
    # class_count dimension, then for each class: bias followed by its weights.
    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as output:
        output.write(f"{CLASS_COUNT} {dimension}\n")
        for class_index in range(CLASS_COUNT):
            output.write(f"{biases[class_index]:.12g}\n")
            output.write(
                " ".join(f"{value:.12g}" for value in weights[class_index])
                + "\n"
            )

    print(f"Classifier weights saved to {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
