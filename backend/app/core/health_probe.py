import argparse
import asyncio
import json
import sys

from app.core.readiness import run_service_readiness


async def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Dependency-aware health probe for service containers."
    )
    parser.add_argument(
        "--service",
        required=True,
        help="Service profile name (api, worker_rq, scheduler, bot).",
    )
    args = parser.parse_args()

    checks, elapsed_ms = await run_service_readiness(args.service)
    all_ok = all(value == "ok" for value in checks.values())

    payload = {
        "service": args.service,
        "status": "ok" if all_ok else "not_ready",
        "checks": checks,
        "elapsed_ms": elapsed_ms,
    }

    print(json.dumps(payload, ensure_ascii=False))

    return 0 if all_ok else 1


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()

