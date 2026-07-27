"""Fixture chung cho test script ảnh: sinh ảnh nhiễu deterministic.

Ảnh nhiễu theo seed có phash cách nhau rất xa (>= 24 bit với các seed nhỏ)
nên dùng làm "ảnh khác nhau" trong test dedup. KHÔNG dùng ảnh màu trơn:
mọi ảnh màu trơn đều có phash 0 → giả-trùng nhau.
"""

import random
from collections.abc import Callable

import pytest
from PIL import Image


@pytest.fixture
def make_noise_image() -> Callable[..., Image.Image]:
    """Factory tạo ảnh nhiễu RGB deterministic theo seed."""

    def _make(seed: int, size: tuple[int, int] = (120, 120)) -> Image.Image:
        rng = random.Random(seed)
        image = Image.new("RGB", size)
        image.putdata(
            [
                (rng.randrange(256), rng.randrange(256), rng.randrange(256))
                for _ in range(size[0] * size[1])
            ]
        )
        return image

    return _make
