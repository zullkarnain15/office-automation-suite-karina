import argparse
from pathlib import Path

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_PNG = SCRIPT_DIR / "app.png"

ICON_SIZES = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]


def resolve_source_path(source: Path) -> Path:
    if source.is_absolute() or source.exists():
        return source.resolve()

    return (SCRIPT_DIR / source).resolve()


def create_multisize_icon(source_png: Path, output_ico: Path | None = None) -> Path:
    source_png = resolve_source_path(source_png)
    output_ico = (
        output_ico.resolve()
        if output_ico is not None
        else source_png.with_suffix(".ico")
    )

    if not source_png.exists():
        raise FileNotFoundError(f"File sumber tidak ditemukan: {source_png}")

    with Image.open(source_png) as image:
        image = image.convert("RGBA")

        if image.width != image.height:
            raise ValueError(
                f"Icon harus berbentuk persegi. "
                f"Ukuran sekarang: {image.width}x{image.height}"
            )

        image.save(
            output_ico,
            format="ICO",
            sizes=ICON_SIZES,
        )

    print(f"Berhasil membuat multi-size icon: {output_ico}")
    return output_ico


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Buat file ICO multi-size dari gambar PNG persegi."
    )
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=DEFAULT_SOURCE_PNG,
        help="File PNG sumber (default: icon_builder/app.png).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Lokasi ICO output (default: nama sumber dengan ekstensi .ico).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    create_multisize_icon(arguments.source, arguments.output)
