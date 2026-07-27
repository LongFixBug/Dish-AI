"""Hợp đồng của sidecar tách chủ thể — phần thuần, không nạp model."""

import base64
import io

import pytest
from fastapi import HTTPException
from PIL import Image

from ml.serving import segment_server


def _png_bytes(size: tuple[int, int], color=(200, 120, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_decode_image_reads_a_valid_png() -> None:
    image = segment_server.decode_image(_b64(_png_bytes((10, 8))))

    assert image.size == (10, 8)
    assert image.mode == "RGB"


@pytest.mark.parametrize("payload", ["", "khong-phai-base64!!", _b64(b"not-an-image")])
def test_decode_image_rejects_broken_payloads(payload: str) -> None:
    with pytest.raises(HTTPException) as error:
        segment_server.decode_image(payload)

    assert error.value.status_code in {413, 422}


def test_decode_image_rejects_oversized_payload(monkeypatch) -> None:
    monkeypatch.setattr(segment_server, "MAX_IMAGE_BYTES", 10)

    with pytest.raises(HTTPException) as error:
        segment_server.decode_image(_b64(_png_bytes((64, 64))))

    assert error.value.status_code == 413


def test_shrink_to_fit_caps_the_longest_side_and_keeps_ratio() -> None:
    shrunk = segment_server.shrink_to_fit(Image.new("RGB", (1000, 500)), 200)

    assert shrunk.size == (200, 100)


def test_shrink_to_fit_never_upscales_a_small_image() -> None:
    original = Image.new("RGB", (80, 40))

    assert segment_server.shrink_to_fit(original, 512).size == (80, 40)


def test_crop_to_subject_trims_the_transparent_border() -> None:
    canvas = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    canvas.paste(Image.new("RGBA", (10, 6), (255, 0, 0, 255)), (12, 20))

    assert segment_server.crop_to_subject(canvas).size == (10, 6)


def test_crop_to_subject_keeps_a_fully_transparent_image_intact() -> None:
    """Tách trượt hoàn toàn thì trả ảnh gốc, không trả ảnh rỗng làm caller vỡ."""
    blank = Image.new("RGBA", (12, 9), (0, 0, 0, 0))

    assert segment_server.crop_to_subject(blank).size == (12, 9)


def test_encode_png_round_trips_transparency() -> None:
    source = Image.new("RGBA", (5, 5), (10, 20, 30, 128))

    decoded = Image.open(io.BytesIO(base64.b64decode(segment_server.encode_png(source))))

    assert decoded.format == "PNG"
    assert decoded.mode == "RGBA"
    assert decoded.getpixel((0, 0))[3] == 128


def test_health_never_loads_the_model() -> None:
    assert segment_server.health() == {
        "status": "ok",
        "model": segment_server.MODEL_NAME,
    }
    assert segment_server._backend is None


def test_segment_uses_the_backend_and_returns_a_cropped_png(monkeypatch) -> None:
    """Toàn bộ đường đi được kiểm bằng backend giả — test không đụng onnxruntime."""

    def fake_remove(image: Image.Image) -> Image.Image:
        canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
        canvas.paste(Image.new("RGBA", (4, 3), (0, 255, 0, 255)), (2, 2))
        return canvas

    monkeypatch.setattr(
        segment_server,
        "_load_backend",
        lambda: segment_server.SegmentBackend(model_name="fake", remove=fake_remove),
    )

    response = segment_server.segment(
        segment_server.SegmentRequest(
            image=_b64(_png_bytes((300, 150))), max_side=100, outline_width=0
        )
    )

    assert (response.width, response.height) == (4, 3)
    assert response.model == "fake"
    decoded = Image.open(io.BytesIO(base64.b64decode(response.image)))
    assert decoded.mode == "RGBA"


def test_segment_reports_a_busy_service_instead_of_leaking_the_error(
    monkeypatch,
) -> None:
    def exploding_remove(_image: Image.Image) -> Image.Image:
        raise RuntimeError("onnxruntime session died")

    monkeypatch.setattr(
        segment_server,
        "_load_backend",
        lambda: segment_server.SegmentBackend(
            model_name="fake", remove=exploding_remove
        ),
    )

    with pytest.raises(HTTPException) as error:
        segment_server.segment(
            segment_server.SegmentRequest(image=_b64(_png_bytes((20, 20))))
        )

    assert error.value.status_code == 503
    assert "onnxruntime" not in str(error.value.detail)


def test_outline_grows_the_canvas_on_every_side() -> None:
    canvas = Image.new("RGBA", (10, 6), (255, 0, 0, 255))

    outlined = segment_server.add_sticker_outline(canvas, width=4)

    assert outlined.size == (18, 14)


def test_outline_paints_white_around_the_subject() -> None:
    """Pixel ngay sát mép chủ thể phải là trắng đục — đó chính là cái viền."""
    canvas = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    canvas.paste(Image.new("RGBA", (8, 8), (0, 0, 255, 255)), (6, 6))

    outlined = segment_server.add_sticker_outline(canvas, width=3)

    # Tâm vẫn là chủ thể, còn vành ngoài đã thành trắng.
    assert outlined.getpixel((13, 13))[:3] == (0, 0, 255)
    ring = outlined.getpixel((13, 7))
    assert ring[3] == 255
    assert ring[:3] == (255, 255, 255)
    # Góc xa vẫn trong suốt, viền không loang ra cả ảnh.
    assert outlined.getpixel((0, 0))[3] == 0


def test_outline_width_zero_leaves_the_image_untouched() -> None:
    canvas = Image.new("RGBA", (9, 9), (1, 2, 3, 255))

    assert segment_server.add_sticker_outline(canvas, width=0).size == (9, 9)


def test_segment_applies_the_outline_when_asked(monkeypatch) -> None:
    def fake_remove(image: Image.Image) -> Image.Image:
        canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
        canvas.paste(Image.new("RGBA", (6, 6), (0, 255, 0, 255)), (4, 4))
        return canvas

    monkeypatch.setattr(
        segment_server,
        "_load_backend",
        lambda: segment_server.SegmentBackend(model_name="fake", remove=fake_remove),
    )

    plain = segment_server.segment(
        segment_server.SegmentRequest(
            image=_b64(_png_bytes((80, 80))), outline_width=0
        )
    )
    bordered = segment_server.segment(
        segment_server.SegmentRequest(
            image=_b64(_png_bytes((80, 80))), outline_width=5
        )
    )

    assert (plain.width, plain.height) == (6, 6)
    assert (bordered.width, bordered.height) == (16, 16)
