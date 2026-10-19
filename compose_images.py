"""Composite PNG layers in order without loading a generation model.

Example: python compose_images.py --files background.png graphic.png -n result
Requires Pillow. Layers must have the same dimensions; the first is the bottom.
"""
import argparse
from pathlib import Path

from PIL import Image


def compose_layers(paths):
    if len(paths) < 2:
        raise ValueError("Provide a background and at least one foreground layer")
    result = None
    for path in paths:
        with Image.open(path) as source:
            layer = source.convert("RGBA")
        if result is None:
            result = layer
        elif layer.size != result.size:
            raise ValueError(
                f"Layer '{path}' has size {layer.size}; expected {result.size}"
            )
        else:
            result = Image.alpha_composite(result, layer)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', nargs='+', required=True, type=Path)
    parser.add_argument('-n', '--name', required=True, type=Path,
                        help='Output PNG path (extension optional); existing files are preserved')
    args = parser.parse_args()
    output = args.name
    if not output.suffix:
        output = output.with_suffix('.png')
    if output.suffix.lower() != '.png':
        parser.error('Output must be PNG to preserve transparency')
    try:
        result = compose_layers(args.files)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as destination:
            result.save(destination, format='PNG')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'Saved: {output}')


if __name__ == '__main__':
    main()
