"""Capture one image from the default camera into the active project directory.

Usage:
    python cli_camera.py
    python cli_camera.py --camera 1
    python cli_camera.py --out receipt.png

The capture is saved as ``camera.png`` in the directory selected by
``project.json``. Press Space, Enter, or click inside the preview to capture;
press Escape or Q to cancel.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lib.wrapp_log import console_log, get_project_directory, load_project_config, read_log_enabled
from lib.wrapp_system import get_platform_system


PROJECT_ROOT = Path(__file__).resolve().parent
WINDOW_TITLE = "Camera – Space/Enter/click to capture, Esc/Q to cancel"
OUTPUT_FILENAME = "camera.png"
PREVIEW_SCALE = 2


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
    parser.add_argument(
        "--out",
        default=OUTPUT_FILENAME,
        metavar="FILE",
        help="image file in the active project directory (default: camera.png)",
    )
    return parser.parse_args()


def open_camera(cv2: object, camera_index: int) -> tuple[object, str]:
    """Open a camera using the platform's preferred OpenCV backend."""

    if camera_index < 0:
        raise ValueError("The camera index must be a non-negative integer.")

    system = get_platform_system()
    if system == "Windows":
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # type: ignore[attr-defined]
        backend_name = "DirectShow"
    elif system == "Linux":
        v4l2_backend = getattr(cv2, "CAP_V4L2", None)
        capture = cv2.VideoCapture(camera_index, v4l2_backend) if v4l2_backend is not None else None
        backend_name = "V4L2"
        if capture is None or not capture.isOpened():
            if capture is not None:
                capture.release()
            capture = cv2.VideoCapture(camera_index)  # type: ignore[attr-defined]
            backend_name = "OpenCV default backend"
    else:
        capture = cv2.VideoCapture(camera_index)  # type: ignore[attr-defined]
        backend_name = "OpenCV default backend"

    if not capture.isOpened():
        capture.release()
        linux_hint = " On Linux, check /dev/videoN and camera permissions." if system == "Linux" else ""
        raise RuntimeError(
            f"Could not open camera with index {camera_index}. "
            f"Check the camera connection and permissions.{linux_hint}"
        )
    return capture, backend_name


def resolve_output_path(project_directory: Path, filename: str) -> Path:
    """Resolve a camera output file without allowing paths outside the project."""

    candidate = Path(filename.strip())
    if not filename.strip() or candidate.is_absolute():
        raise ValueError("--out must be a non-empty path relative to the active project directory.")
    output_path = (project_directory / candidate).resolve()
    if not output_path.is_relative_to(project_directory.resolve()):
        raise ValueError("--out must stay inside the active project directory.")
    return output_path


def capture_image(output_path: Path, camera_index: int) -> Path | None:
    """Show the live preview and return the saved image path, or None on cancel."""

    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "The opencv-python package is missing. Run: python -m pip install -r requirements.txt"
        ) from error

    system = get_platform_system()
    if system == "Linux" and not ("DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ):
        raise RuntimeError("Camera preview requires a graphical Linux session (DISPLAY or WAYLAND_DISPLAY).")

    camera, backend_name = open_camera(cv2, camera_index)
    capture_requested = False
    preview_size_set = False
    mouse_callback_set = False

    def request_capture(event: int, _x: int, _y: int, _flags: int, _param: object) -> None:
        nonlocal capture_requested
        if event == cv2.EVENT_LBUTTONUP:
            capture_requested = True

    try:
        try:
            cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
        except cv2.error as error:
            raise RuntimeError(
                "OpenCV could not create the camera preview window. On GNOME/Wayland, try: "
                "QT_QPA_PLATFORM=xcb python3 cli_camera.py"
            ) from error
        print(f"Camera {camera_index} preview started on {system} using {backend_name}.")
        print("Capture: Space, Enter, or click in the preview. Cancel: Esc or Q.")

        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                raise RuntimeError("Could not read an image from the camera.")

            if not preview_size_set:
                height, width = frame.shape[:2]
                cv2.resizeWindow(WINDOW_TITLE, width * PREVIEW_SCALE, height * PREVIEW_SCALE)
                preview_size_set = True
            try:
                cv2.imshow(WINDOW_TITLE, frame)
            except cv2.error as error:
                raise RuntimeError(
                    "OpenCV could not display the camera preview. On GNOME/Wayland, try: "
                    "QT_QPA_PLATFORM=xcb python3 cli_camera.py"
                ) from error
            if not mouse_callback_set:
                # Some Qt backends attach a window handle only after the first imshow().
                # Mouse control is optional, so keyboard capture remains available.
                try:
                    cv2.setMouseCallback(WINDOW_TITLE, request_capture)
                    mouse_callback_set = True
                except cv2.error:
                    print("WARNING: Mouse capture is unavailable; use Space or Enter to capture.")
                    mouse_callback_set = True
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
        project_config = load_project_config(PROJECT_ROOT)
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        output_path = resolve_output_path(project_directory, arguments.out)
        log_enabled = read_log_enabled(PROJECT_ROOT / "project.json")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    with console_log(project_directory, "cli_camera.py", log_enabled):
        try:
            output_path = capture_image(output_path, arguments.camera)
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
