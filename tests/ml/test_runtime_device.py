import pytest

from ml.inference.runtime_device import resolve_inference_device


def test_auto_prefers_cuda_over_mps_and_cpu() -> None:
    assert (
        resolve_inference_device(
            requested="auto",
            cuda_available=True,
            mps_available=True,
        )
        == "cuda"
    )


@pytest.mark.parametrize(
    ("cuda_available", "mps_available", "expected"),
    [
        (False, True, "mps"),
        (False, False, "cpu"),
    ],
)
def test_auto_falls_back_to_available_accelerator(
    cuda_available: bool,
    mps_available: bool,
    expected: str,
) -> None:
    assert (
        resolve_inference_device(
            requested="auto",
            cuda_available=cuda_available,
            mps_available=mps_available,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("requested", "cuda_available", "mps_available", "message"),
    [
        ("cuda", False, False, "CUDA không sẵn sàng"),
        ("mps", False, False, "MPS không sẵn sàng"),
    ],
)
def test_explicit_unavailable_accelerator_fails_clearly(
    requested: str,
    cuda_available: bool,
    mps_available: bool,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_inference_device(
            requested=requested,
            cuda_available=cuda_available,
            mps_available=mps_available,
        )
