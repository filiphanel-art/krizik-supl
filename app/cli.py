"""Příkazové rozhraní (CLI) pro Suplování Viewer: serve a export-static."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from app.config import load_config
from app.static_export import export_static_site
from app.web import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="krizik-supl",
        description="Školní zobrazení suplování (Suplování Viewer)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Cesta ke konfiguračnímu souboru config.yaml",
    )

    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Spustí webový server a sledování složky")
    serve_parser.add_argument("--host", type=str, default=None, help="IP adresa serveru")
    serve_parser.add_argument("--port", type=int, default=None, help="Port serveru")

    export_parser = subparsers.add_parser(
        "export-static",
        help="Vygeneruje statickou anonymizovanou verzi (HTML+JSON) do složky dist/",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        default=Path("./dist"),
        help="Cílová složka pro statický export (výchozí: ./dist)",
    )
    export_parser.add_argument(
        "--watch-dir",
        type=Path,
        default=None,
        help="Volitelná cesta ke složce s HTML exporty",
    )

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "export-static":
        if args.watch_dir is not None:
            cfg = cfg.model_copy(update={"watch_dir": args.watch_dir})
        stats = export_static_site(cfg, output_dir=args.output)
        print(
            f"Statický anonymizovaný export dokončen do '{args.output}': "
            f"{stats['days']} dnů, {stats['changes']} změn."
        )
        return 0

    host = getattr(args, "host", None) or cfg.host
    port = getattr(args, "port", None) or cfg.port
    app = create_app(config=cfg, start_watcher=True)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
