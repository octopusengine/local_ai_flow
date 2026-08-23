"""Reusable image-path and Ollama image-payload helpers."""

from __future__ import annotations

import base64
from pathlib import Path


__version__ = "0.26.02"


def resolve_project_file(
    filename: str | Path,
    project_directory: Path,
    description: str,
) -> Path:
    """Resolve a file anywhere inside the configured project directory.

    Absolute paths are accepted only when they remain within the active
    project directory. This permits safe project subdirectories such as
    ``src/`` while rejecting paths outside the project.
    """

    resolved_directory = project_directory.resolve()
    candidate = Path(filename)
    file_path = candidate.resolve() if candidate.is_absolute() else (resolved_directory / candidate).resolve()
    try:
        file_path.relative_to(resolved_directory)
    except ValueError as error:
        raise ValueError(
            f"The {description} must be inside the project directory from project.json."
        ) from error
    return file_path


def resolve_image_path(
    image_argument: str | None,
    project_directory: Path,
    default_input_file: str,
    supported_extensions: set[str],
    *,
    fallback_extensions: set[str] | None = None,
) -> Path:
    """Return the requested, default, or first fallback image in a project directory."""

    normalized_extensions = {extension.lower() for extension in supported_extensions}
    if not normalized_extensions:
        raise ValueError("At least one supported image extension is required.")

    def validate_image(path: Path) -> Path:
        if path.suffix.lower() not in normalized_extensions:
            extensions = ", ".join(sorted(normalized_extensions))
            raise ValueError(f"The input image must use one of these extensions: {extensions}.")
        if not path.is_file():
            raise ValueError(f"Input image was not found: {path}")
        return path

    if image_argument:
        return validate_image(resolve_project_file(image_argument, project_directory, "input image"))

    default_image = resolve_project_file(default_input_file, project_directory, "default input file")
    if default_image.is_file():
        return validate_image(default_image)

    if fallback_extensions is None:
        raise ValueError(f"Input image was not found: {default_image}")

    normalized_fallback_extensions = {extension.lower() for extension in fallback_extensions}
    images = sorted(
        path
        for path in project_directory.resolve().iterdir()
        if path.is_file() and path.suffix.lower() in normalized_fallback_extensions
    )
    if images:
        return images[0]

    extensions = ", ".join(sorted(normalized_fallback_extensions))
    raise ValueError(
        f"No image was found in {project_directory.resolve()}. "
        f"Expected {default_input_file} or another image with one of these extensions: {extensions}."
    )


def resize_image_for_request(
    image_bytes: bytes,
    max_image_size: int,
) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    """Resize an image to its maximum side and return bytes plus original and target sizes."""

    if max_image_size <= 0:
        raise ValueError("The maximum image size must be positive.")

    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "Image resizing requires opencv-python. Run: python -m pip install -r requirements.txt"
        ) from error

    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Could not decode the input image.")
    height, width = image.shape[:2]
    original_size = (width, height)
    if max(width, height) <= max_image_size:
        return image_bytes, original_size, original_size

    scale = max_image_size / max(width, height)
    target_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized = cv2.resize(image, target_size, interpolation=cv2.INTER_AREA)
    encoded, resized_bytes = cv2.imencode(".png", resized)
    if not encoded:
        raise ValueError("Could not encode the resized image.")
    return resized_bytes.tobytes(), original_size, target_size


def image_bytes_to_ollama_base64(image_bytes: bytes) -> str:
    """Encode image bytes for Ollama's JSON ``images`` field."""

    return base64.b64encode(image_bytes).decode("ascii")
