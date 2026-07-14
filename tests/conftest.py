"""Shared fixtures: tiny deterministic corpora with known diversity shapes."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from samey.reader import Record  # noqa: E402


def make_records(texts):
    """Build Record objects with sequential indices, like the reader does."""
    return [Record(index=i, source="<test>", text=t) for i, t in enumerate(texts)]


@pytest.fixture
def diverse_texts():
    """Ten sentences with almost no shared phrases: a healthy corpus."""
    return [
        "The lighthouse keeper counted gulls before every storm.",
        "Quantum annealing struggles with dense constraint graphs.",
        "She braided copper wire into the shape of a fern.",
        "Fermented plum vinegar sharpens an otherwise flat broth.",
        "Volcanic soil drains too fast for shallow-rooted lettuce.",
        "The violinist tuned to the hum of the refrigerator.",
        "Border collies map their pastures like chess boards.",
        "Rust never sleeps, but zinc coatings buy decades.",
        "A single misplaced semicolon toppled the billing system.",
        "Cave divers navigate by touch when silt blooms rise.",
    ]


@pytest.fixture
def collapsed_texts():
    """Ten records dominated by one template: a collapsed corpus."""
    return [
        "As a helpful assistant, I would be happy to help you today.",
        "As a helpful assistant, I would be happy to help you today.",
        "As a helpful assistant, I would be happy to help you today!",
        "As a helpful assistant, I would be happy to help you now.",
        "As a helpful assistant, I would be happy to assist you today.",
        "As a helpful assistant, I would be happy to help you today.",
        "As a helpful assistant, I am happy to help you today.",
        "As a helpful assistant, I would be happy to help you today.",
        "As a helpful assistant, I would be happy to help.",
        "As a helpful assistant, I would be happy to help you today.",
    ]


@pytest.fixture
def diverse_records(diverse_texts):
    return make_records(diverse_texts)


@pytest.fixture
def collapsed_records(collapsed_texts):
    return make_records(collapsed_texts)
