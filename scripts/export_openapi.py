"""Export the API contract from the application factory without starting a server."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from baseera.main import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("packages/contracts/openapi.json"),
        help="Destination JSON file (default: packages/contracts/openapi.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="baseera-openapi-") as temporary:
        root = Path(temporary)
        application = create_app(
            database_url=f"sqlite:///{root / 'contract.db'}",
            artifact_root=root / "artifacts",
            testing=True,
            seed_demo=False,
        )
        contract = application.openapi()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "exported",
                "output": str(args.output),
                "paths": len(contract.get("paths", {})),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
