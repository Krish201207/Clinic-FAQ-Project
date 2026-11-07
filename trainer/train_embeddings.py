"""NumPy-optimized Skip-gram with negative sampling trainer."""

import math
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data.txt"
OUTPUT_FILE = BASE_DIR / "Embeddings.vec"

DIM = 50
WINDOW = 2
NEGATIVE_SAMPLES = 5
EPOCHS = 10
LEARNING_RATE = 0.025
SEED = None

TOKEN_RE = re.compile(r"[^a-zA-Z0-9']+")


def tokenize(line):
    return TOKEN_RE.sub(" ", line.lower()).split()


def sigmoid(value):
    if value >= 0.0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def load_sentences(path):
    sentences = []
    counts = Counter()

    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            words = tokenize(line)
            if words:
                sentences.append(words)
                counts.update(words)

    return sentences, counts


def build_negative_cdf(vocabulary, counts):
    sampling_weights = np.array(
        [counts[word] ** 0.75 for word in vocabulary], dtype=np.float64
    )
    probabilities = sampling_weights / sampling_weights.sum()
    cdf = np.cumsum(probabilities)
    cdf[-1] = 1.0
    return cdf


def sample_negative(positive_target, cdf, rng):
    while True:
        draw = rng.random()
        sampled = min(int(np.searchsorted(cdf, draw, side="left")), len(cdf) - 1)
        if sampled != positive_target or len(cdf) == 1:
            return sampled


def train_binary(center, target, label, input_vectors, output_vectors, learning_rate):
    input_vector = input_vectors[center]
    output_vector = output_vectors[target]

    score = np.dot(input_vector, output_vector)
    prediction = sigmoid(float(score))

    if label == 1.0:
        loss = -math.log(max(prediction, 1e-15))
    else:
        loss = -math.log(max(1.0 - prediction, 1e-15))

    error = (prediction - label) * learning_rate

    # Preserve the original simultaneous-update behavior.
    old_input = input_vector.copy()
    old_output = output_vector.copy()

    input_vectors[center] -= error * old_output
    output_vectors[target] -= error * old_input

    return loss


def main():
    rng = random.Random(SEED)
    sentences, counts = load_sentences(INPUT_FILE)

    vocabulary = sorted(counts)
    word_to_id = {word: index for index, word in enumerate(vocabulary)}
    vocab_size = len(vocabulary)

    encoded_sentences = [
        [word_to_id[word] for word in sentence]
        for sentence in sentences
    ]

    negative_cdf = build_negative_cdf(vocabulary, counts)

    input_vectors = np.array(
        [
            [rng.uniform(-0.5 / DIM, 0.5 / DIM) for _ in range(DIM)]
            for _ in range(vocab_size)
        ],
        dtype=np.float64,
    )
    output_vectors = np.zeros((vocab_size, DIM), dtype=np.float64)

    pairs = []
    for sentence in encoded_sentences:
        length = len(sentence)
        for center_position, center_id in enumerate(sentence):
            left = max(0, center_position - WINDOW)
            right = min(length - 1, center_position + WINDOW)
            for context_position in range(left, right + 1):
                if context_position != center_position:
                    pairs.append((center_id, sentence[context_position]))

    print(f"Training file: {INPUT_FILE.name}")
    print(f"Sentences: {len(encoded_sentences)}")
    print(f"Vocabulary: {vocab_size}")
    print(f"Training pairs: {len(pairs)}")
    print(f"Dimensions: {DIM}")
    print(f"Negative samples per pair: {NEGATIVE_SAMPLES}")
    print(f"Epochs: {EPOCHS}")

    for epoch in range(EPOCHS):
        rng.shuffle(pairs)
        total_loss = 0.0
        updates = 0

        for center, positive in pairs:
            total_loss += train_binary(
                center, positive, 1.0,
                input_vectors, output_vectors, LEARNING_RATE
            )
            updates += 1

            for _ in range(NEGATIVE_SAMPLES):
                negative = sample_negative(positive, negative_cdf, rng)
                total_loss += train_binary(
                    center, negative, 0.0,
                    input_vectors, output_vectors, LEARNING_RATE
                )
                updates += 1

        print(
            f"Epoch {epoch + 1}/{EPOCHS} | "
            f"average loss: {total_loss / updates:.6f}"
        )

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as output:
        output.write(f"{vocab_size} {DIM}\n")
        for word, vector in zip(vocabulary, input_vectors):
            output.write(word)
            output.write(" ")
            output.write(" ".join(f"{value:.9f}" for value in vector))
            output.write("\n")

    print(f"\nEmbeddings saved to {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
