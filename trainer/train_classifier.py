"""NumPy-optimized softmax classifier trainer."""

import math
import random
import re
from pathlib import Path

import numpy as np

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
SEED = None

TOKEN_RE = re.compile(r"[^a-zA-Z0-9']+")


def tokenize(text):
    return TOKEN_RE.sub(" ", text.lower()).split()


def load_embeddings(path):
    embeddings = {}
    with path.open("r", encoding="utf-8", errors="replace") as file:
        vocabulary_size, dimension = map(int, file.readline().split())

        for _ in range(vocabulary_size):
            parts = file.readline().split()
            word = parts[0]
            embeddings.setdefault(
                word, np.asarray(parts[1:], dtype=np.float64)
            )

    return embeddings, dimension


def make_sentence_vector(text, embeddings, dimension):
    result = np.zeros(dimension, dtype=np.float64)
    known = 0

    for word in tokenize(text):
        vector = embeddings.get(word)
        if vector is not None:
            result += vector
            known += 1

    if known == 0:
        return result

    result /= known
    norm = np.linalg.norm(result)

    if norm > 1e-12:
        result /= norm

    return result


def softmax(logits):
    exponentials = np.exp(logits - np.max(logits))
    return exponentials / np.sum(exponentials)


def load_training_examples(path, embeddings, dimension):
    examples = []

    with path.open("r", encoding="utf-8", errors="replace") as file:
        for raw_line in file:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue

            label_text, question = line.split("\t", 1)
            label_text = label_text.strip()

            features = make_sentence_vector(question, embeddings, dimension)
            if np.dot(features, features) > 1e-20:
                examples.append((features, LABELS[label_text]))

    return examples


def main():
    rng = random.Random(SEED)
    embeddings, dimension = load_embeddings(EMBEDDING_FILE)
    examples = load_training_examples(TRAINING_FILE, embeddings, dimension)

    weights = np.zeros((CLASS_COUNT, dimension), dtype=np.float64)
    biases = np.zeros(CLASS_COUNT, dtype=np.float64)

    print(f"Loaded embeddings: {len(embeddings)}")
    print(f"Embedding dimensions: {dimension}")
    print(f"Training examples: {len(examples)}")
    print(f"Classes: {', '.join(LABELS)}")

    for epoch in range(EPOCHS):
        rng.shuffle(examples)
        total_loss = 0.0

        for features, correct_label in examples:
            logits = weights @ features + biases
            probabilities = softmax(logits)
            total_loss -= math.log(max(probabilities[correct_label], 1e-12))

            # Keep online updates in the original class-by-class order.
            for class_index in range(CLASS_COUNT):
                error = probabilities[class_index] - (
                    1.0 if class_index == correct_label else 0.0
                )
                biases[class_index] -= LEARNING_RATE * error

                gradient = error * features + L2 * weights[class_index]
                weights[class_index] -= LEARNING_RATE * gradient

        print(
            f"Epoch {epoch + 1}/{EPOCHS} "
            f"Loss: {total_loss / len(examples):.6f}"
        )

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
