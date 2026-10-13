"""Isolated release-gate verification for OAS-K 1.0.17."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_VERIFIER = Path(__file__).with_name("verify_release_1_0_16.py")


def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "oas_k_release_verifier_1_0_16",
        BASE_VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Tidak dapat memuat verifier: {BASE_VERIFIER}")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.VERSION = "1.0.17"
    verifier.PREVIOUS_VERSION = "1.0.15"
    verifier.CORE_SCHEMA = 4
    verifier.PRODUCTION_ANALYTICS_SCHEMA = 9
    verifier.TARGET_ANALYTICS_SCHEMA = 9
    verifier.main()


if __name__ == "__main__":
    main()
