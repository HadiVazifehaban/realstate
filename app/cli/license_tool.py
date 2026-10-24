"""Command-line tooling for the commercial license lifecycle.

Sub-commands
------------
``keygen``       Generate the RSA-4096 signing key pair (run this ONCE on the hub;
                 the private key never leaves the license server).
``fingerprint``  Print this machine's hardware fingerprint hash (for activation).
``issue``        Sign a license token for an agency bound to a fingerprint.
``verify``       Verify + decode the license currently installed on this node.
``install``      Copy a token file into the node license path.

Examples
--------
    python -m app.cli.license_tool keygen --out-dir data/keys
    python -m app.cli.license_tool fingerprint
    python -m app.cli.license_tool issue --agency "املاک آفتاب" \\
        --fingerprint <hash> --days 365 --max-users 10 --out node.lic
    python -m app.cli.license_tool verify
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.licensing import (
    LicenseManager,
    LicensePayload,
    collect_hardware_fingerprint,
    encode_license,
    generate_keypair,
)


def _cmd_keygen(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    private_pem, public_pem = generate_keypair()
    private_path = out_dir / "license_private.pem"
    public_path = out_dir / "license_public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    try:
        private_path.chmod(0o600)
    except OSError:
        pass
    print(f"[OK] private key -> {private_path} (keep SECRET on the hub)")
    print(f"[OK] public  key -> {public_path} (embed on every node)")
    return 0


def _cmd_fingerprint(args: argparse.Namespace) -> int:
    settings = get_settings()
    fp = collect_hardware_fingerprint(settings.machine_fingerprint_override or None)
    print(
        json.dumps(
            {
                "fingerprint_hash": fp.hash(),
                "components": fp.component_count,
                "canonical": fp.canonical(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cmd_issue(args: argparse.Namespace) -> int:
    settings = get_settings()
    private_path = (
        Path(args.private_key)
        if args.private_key
        else settings.resolve_path(settings.license_private_key_file)
    )
    if not private_path.exists():
        print(f"[ERR] private key not found: {private_path}", file=sys.stderr)
        return 2

    now = int(time.time())
    payload = LicensePayload(
        license_id=args.license_id or f"AVG-{now}",
        agency_name=args.agency,
        machine_fingerprint_hash=args.fingerprint,
        max_concurrent_users=args.max_users,
        issued_at=now,
        expires_at=now + args.days * 86400,
        features=args.features or [],
    )
    token = encode_license(payload, private_path.read_bytes())
    out = Path(args.out) if args.out else Path("node.lic")
    out.write_text(token, encoding="utf-8")
    print(f"[OK] license issued -> {out}")
    print(f"     agency        : {payload.agency_name}")
    print(f"     license id    : {payload.license_id}")
    print(f"     max users     : {payload.max_concurrent_users}")
    print(f"     expires       : {payload.expires_at_dt.isoformat()}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    settings = get_settings()
    manager = LicenseManager(
        license_file=(
            Path(args.license) if args.license else settings.resolve_path(settings.license_file)
        ),
        public_key_file=settings.resolve_path(settings.license_public_key_file),
        grace_days=settings.offline_grace_days,
        fingerprint_override=settings.machine_fingerprint_override or None,
    )
    evaluation = manager.evaluate()
    print(f"status : {evaluation.status.value}")
    print(f"usable : {evaluation.is_usable}")
    print(f"reason : {evaluation.reason}")
    if evaluation.offline_grace_deadline:
        dt = datetime.fromtimestamp(evaluation.offline_grace_deadline, tz=timezone.utc)
        print(f"grace  : {dt.isoformat()}")
    if evaluation.payload:
        print(f"agency : {evaluation.payload.agency_name}")
        print(f"expires: {evaluation.payload.expires_at_dt.isoformat()}")
    return 0 if evaluation.is_usable else 1


def _cmd_install(args: argparse.Namespace) -> int:
    settings = get_settings()
    src = Path(args.token)
    if not src.exists():
        print(f"[ERR] token file not found: {src}", file=sys.stderr)
        return 2
    dest = settings.resolve_path(settings.license_file)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8").strip(), encoding="utf-8")
    try:
        dest.chmod(0o600)
    except OSError:
        pass
    print(f"[OK] installed license -> {dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="avg-license", description="AVG license tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("keygen", help="generate the RSA-4096 signing key pair")
    p.add_argument("--out-dir", default="data/keys")
    p.set_defaults(func=_cmd_keygen)

    p = sub.add_parser("fingerprint", help="print this machine's fingerprint hash")
    p.set_defaults(func=_cmd_fingerprint)

    p = sub.add_parser("issue", help="sign a license token")
    p.add_argument("--agency", required=True)
    p.add_argument("--fingerprint", required=True)
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--max-users", type=int, default=5)
    p.add_argument("--license-id", default=None)
    p.add_argument("--features", nargs="*", default=[])
    p.add_argument("--private-key", default=None)
    p.add_argument("--out", default="node.lic")
    p.set_defaults(func=_cmd_issue)

    p = sub.add_parser("verify", help="verify the installed license")
    p.add_argument("--license", default=None)
    p.set_defaults(func=_cmd_verify)

    p = sub.add_parser("install", help="install a token file into the node path")
    p.add_argument("token")
    p.set_defaults(func=_cmd_install)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
