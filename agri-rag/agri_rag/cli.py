"""CLI: `python -m agri_rag.cli ingest|ask|serve`."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from .config import get_settings
from .container import build_container
from .ingestion.indexer import index_directory


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="agri_rag")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="chunk + embed + index the knowledge directory")
    ing.add_argument("--dir", default=None)
    ing.add_argument("--reset", action="store_true", help="drop the collection first")
    ask = sub.add_parser("ask", help="ask one question from the terminal (streams)")
    ask.add_argument("question")
    ask.add_argument("--crop", default=None)
    ask.add_argument("--farm-json", default=None, help="path to a FarmContext JSON file")
    srv = sub.add_parser("serve", help="run the API")
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    s = get_settings()

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("agri_rag.api.app:app_factory", factory=True, host=args.host, port=args.port)
        return

    c = build_container(s)
    if args.cmd == "ingest":
        report = index_directory(args.dir or s.knowledge_dir, c.store, s, reset=args.reset)
        print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))
    else:
        from .domain.farm import FarmContext

        farm = None
        if args.farm_json:
            with open(args.farm_json, encoding="utf-8") as f:
                farm = FarmContext.model_validate_json(f.read())

        async def run() -> None:
            async for ev in c.pipeline.stream(args.question, farm=farm, crop=args.crop):
                if ev["type"] == "token":
                    print(ev["text"], end="", flush=True)
                elif ev["type"] == "sources":
                    print("المصادر:", ", ".join(f"[{x['id']}] {x['title']}" for x in ev["sources"]), "\n")
                else:
                    print("\n\n", ev["timings"])

        asyncio.run(run())


if __name__ == "__main__":
    main()
