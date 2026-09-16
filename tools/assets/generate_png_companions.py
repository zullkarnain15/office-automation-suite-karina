"""Generate deterministic transparent PNG companions from repository ICOs."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "assets" / "icons"
DEFAULT_OUTPUT = DEFAULT_SOURCE / "png"
BACKGROUND_TOLERANCE = 18


def _close_color(left: tuple[int, int, int], right: tuple[int, int, int]) -> bool:
    return all(abs(a - b) <= BACKGROUND_TOLERANCE for a, b in zip(left, right))


def _clear_connected_edge_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] == 0:
        return rgba

    width, height = rgba.size
    pixels = rgba.load()
    corner_colors = {
        pixels[0, 0][:3],
        pixels[width - 1, 0][:3],
        pixels[0, height - 1][:3],
        pixels[width - 1, height - 1][:3],
    }
    if not all(min(color) >= 240 for color in corner_colors):
        return rgba

    queue: deque[tuple[int, int]] = deque()
    seen: set[tuple[int, int]] = set()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
            continue
        seen.add((x, y))
        current = pixels[x, y]
        if current[3] == 0 or not any(
            _close_color(current[:3], corner) for corner in corner_colors
        ):
            continue
        pixels[x, y] = (current[0], current[1], current[2], 0)
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return rgba


def convert(source: Path, output: Path, *, size: int, overwrite: bool) -> bool:
    if output.exists() and not overwrite:
        return False
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        image = ImageOps.contain(image, (size, size), Image.Resampling.NEAREST)
        alpha = image.getchannel("A").point(lambda value: 0 if value < 8 else value)
        image.putalpha(alpha)
        image = _clear_connected_edge_background(image)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(
            image, ((size - image.width) // 2, (size - image.height) // 2)
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, "PNG", optimize=True)
    print(f"{source} -> {output}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--size", type=int, default=22)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.size <= 0:
        parser.error("--size must be positive")
    for source in sorted(args.source.glob("*.ico")):
        convert(
            source,
            args.output / f"{source.stem}.png",
            size=args.size,
            overwrite=args.overwrite,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
