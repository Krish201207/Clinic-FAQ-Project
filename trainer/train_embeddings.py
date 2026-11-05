"""
Pure-Python replacement for train_skipgram_negative_sampling.cpp.

Matches the C++ training logic:
- one input line is one sentence; windows never cross lines
- lowercase + keep letters/digits/apostrophes
- deterministic alphabetical vocabulary
- 50-dimensional input/output vectors
- context window = 2
- 5 negative samples per positive pair
- negative distribution proportional to count(word)^0.75
- input vectors initialized uniformly in [-0.5 / DIM, 0.5 / DIM]
- output vectors initialized to zero
- sigmoid + binary cross-entropy updates
- 10 epochs, learning rate 0.025
- writes the input vectors in the same word2vec-text format

Run: python train_embeddings.py
Input:  data.txt
Output: Embeddings.vec
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data.txt"
OUTPUT_FILE = BASE_DIR / "Embeddings.vec"

DIM = 50
WINDOW = 2
NEGATIVE_SAMPLES = 5
EPOCHS = 10
LEARNING_RATE = 0.025
SEED = None  # Set an integer (e.g. 42) for repeatable training runs.

TOKEN_RE = re.compile(r"[^a-zA-Z0-9']+")


def tokenize(line: str) -> list[str]:
    return TOKEN_RE.sub(" ", line.lower()).split()


def sigmoid(value: float) -> float:
    # Numerically stable equivalent of the C++ sigmoid.
    if value >= 0.0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def load_sentences(path: Path) -> tuple[list[list[str]], Counter[str]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Cannot open {path.name}. Put it beside train_embeddings.py."
        )

    sentences: list[list[str]] = []
    counts: Counter[str] = Counter()

    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            words = tokenize(line)
            if words:
                sentences.append(words)
                counts.update(words)

    if not sentences:
        raise ValueError("Training corpus is empty or contains no readable words.")

    return sentences, counts


def build_negative_cdf(vocabulary: list[str], counts: Counter[str]) -> list[float]:
    # P(word) = count(word)^0.75 / sum(counts^0.75)
    sampling_weights = [counts[word] ** 0.75 for word in vocabulary]
    total = sum(sampling_weights)

    cdf: list[float] = []
    cumulative = 0.0
    for weight in sampling_weights:
        cumulative += weight / total
        cdf.append(cumulative)

    cdf[-1] = 1.0
    return cdf


def sample_negative(
    positive_target: int,
    cdf: list[float],
    rng: random.Random,
) -> int:
    # Equivalent to lower_bound on the C++ cumulative distribution.
    while True:
        draw = rng.random()
        low, high = 0, len(cdf)
        while low < high:
            middle = (low + high) // 2
            if cdf[middle] < draw:
                low = middle + 1
            else:
                high = middle
        sampled = min(low, len(cdf) - 1)
        if sampled != positive_target or len(cdf) == 1:
            return sampled


def train_binary(
    center: int,
    target: int,
    label: float,
    input_vectors: list[list[float]],
    output_vectors: list[list[float]],
    learning_rate: float,
) -> float:
    # Dot product and sigmoid prediction.
    score = sum(
        input_vectors[center][d] * output_vectors[target][d]
        for d in range(DIM)
    )
    prediction = sigmoid(score)

    # Binary cross-entropy loss.
    if label == 1.0:
        loss = -math.log(max(prediction, 1e-15))
    else:
        loss = -math.log(max(1.0 - prediction, 1e-15))

    # Snapshot both vectors so both updates use pre-update values,
    # matching the C++ trainBinary lambda.
    error = (prediction - label) * learning_rate
    old_input = input_vectors[center].copy()
    old_output = output_vectors[target].copy()

    for d in range(DIM):
        input_vectors[center][d] -= error * old_output[d]
        output_vectors[target][d] -= error * old_input[d]

    return loss


def main() -> None:
    rng = random.Random(SEED)
    sentences, counts = load_sentences(INPUT_FILE)

    # The C++ negative-sampling version sorts vocabulary alphabetically.
    vocabulary = sorted(counts)
    word_to_id = {word: index for index, word in enumerate(vocabulary)}
    vocab_size = len(vocabulary)

    if vocab_size < 2:
        raise ValueError("The corpus must contain at least two unique words.")

    encoded_sentences = [
        [word_to_id[word] for word in sentence]
        for sentence in sentences
    ]

    negative_cdf = build_negative_cdf(vocabulary, counts)

    # Input matrix random; output/context matrix starts at zero.
    input_vectors = [
        [rng.uniform(-0.5 / DIM, 0.5 / DIM) for _ in range(DIM)]
        for _ in range(vocab_size)
    ]
    output_vectors = [
        [0.0 for _ in range(DIM)]
        for _ in range(vocab_size)
    ]

    # Generate center-context pairs without crossing sentence boundaries.
    pairs: list[tuple[int, int]] = []
    for sentence in encoded_sentences:
        length = len(sentence)
        for center_position, center_id in enumerate(sentence):
            left = max(0, center_position - WINDOW)
            right = min(length - 1, center_position + WINDOW)
            for context_position in range(left, right + 1):
                if context_position == center_position:
                    continue
                pairs.append((center_id, sentence[context_position]))

    if not pairs:
        raise ValueError("Not enough words to create Skip-gram training pairs.")

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

    # Output format expected by clinic_classifier.py:
    # first line: vocabulary_size dimensions
    # then one word and DIM floats per line.
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
