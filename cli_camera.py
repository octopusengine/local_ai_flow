"""Capture one image from the default camera into the active project directory.

Usage:
    python cli_camera.py
    python cli_camera.py --camera 1

The capture is saved as ``camera.png`` in the directory selected by
``project.json``. Press Space, Enter, or click inside the preview to capture;
press Escape or Q to cancel.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lib.wrapp_cli_log import load_project_directory, project_log, read_log_enabled


PROJECT_ROOT = Path(__file__).resolve().parent
CLI_CONFIG_PATH = PROJECT_ROOT / "cli_camera.json"
WINDOW_TITLE = "Camera – Space/Enter/click to capture, Esc/Q to cancel"
OUTPUT_FILENAME = "camera.png"


def parse_arguments() -> argparse.Namespace:
    """Read the optional camera device index."""

    parser = argparse.ArgumentParser(
        description=(
            "Show a camera preview and save the image as camera.png in the "
            "project directory selected by project.json."
        )
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="camera index (default: 0)",
    )
    return parser.parse_args()


def open_camera(cv2: object, camera_index: int) -> object:
    """Open a camera, preferring the stable Windows DirectShow backend."""

    if camera_index < 0:
        raise ValueError("The camera index must be a non-negative integer.")

    if os.name == "nt":
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # type: ignore[attr-defined]
    else:
        capture = cv2.VideoCapture(camera_index)  # type: ignore[attr-defined]

    if not capture.isOpened():
        capture.release()
        raise RuntimeError(
            f"Could not open camera with index {camera_index}. "
            "Check the camera connection and permissions."
        )
    return capture


def capture_image(project_directory: Path, camera_index: int) -> Path | None:
    """Show the live preview and return the saved image path, or None on cancel."""

    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "The opencv-python package is missing. Run: python -m pip install -r requirements.txt"
        ) from error

    output_path = project_directory / OUTPUT_FILENAME
    camera = open_camera(cv2, camera_index)
    capture_requested = False

    def request_capture(event: int, _x: int, _y: int, _flags: int, _param: object) -> None:
        nonlocal capture_requested
        if event == cv2.EVENT_LBUTTONUP:
            capture_requested = True

    try:
        cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(WINDOW_TITLE, request_capture)
        print(f"Camera {camera_index} preview started.")
        print("Capture: Space, Enter, or click in the preview. Cancel: Esc or Q.")

        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError("Could not read an image from the camera.")

            cv2.imshow(WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF
            if capture_requested or key in (13, 32):
                if not cv2.imwrite(str(output_path), frame):
                    raise RuntimeError(f"Could not save the image to {output_path}.")
                return output_path
            if key in (27, ord("q"), ord("Q")):
                return None
    finally:
        camera.release()
        cv2.destroyAllWindows()


def main() -> int:
    """Run the camera capture command."""

    try:
        arguments = parse_arguments()
        project_directory = load_project_directory(PROJECT_ROOT)
        log_enabled = read_log_enabled(CLI_CONFIG_PATH)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with project_log(project_directory, "cli_camera.py", log_enabled):
        try:
            output_path = capture_image(project_directory, arguments.camera)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

        if output_path is None:
            print("Image was not saved.")
            return 0

        print(f"Saved: {output_path}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
