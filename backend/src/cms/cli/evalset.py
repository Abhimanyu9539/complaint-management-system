"""CLI entrypoint for building and verifying the eval golden dataset.

Two commands, and only the first costs money:

    cms-evalset build     # seed corpus -> tests/evals/data/goldens.json
    cms-evalset verify    # are those goldens' own sources retrievable?

`build` is one `generate_goldens_from_docs` call (see `cms.evals.build`). It
replaces the previous three-step `export-contexts` / `deepeval generate` /
`annotate` sequence, which existed only to work around the contexts path's
missing `source_files` parameter.

`verify` is separate because it needs Qdrant while `build` needs only OpenAI —
coupling them would let a Qdrant outage waste a paid synthesis run.
"""

import argparse
import logging
import sys
import tempfile
from pathlib import Path

# `cms.config` must be imported before anything builds an HTTPS client: it
# injects the OS trust store into ssl, without which every OpenAI call dies
# behind this machine's TLS-intercepting proxy. `export_env` is the other half —
# deepeval reads OPENAI_API_KEY from the process environment and knows nothing
# about pydantic-settings, and `build` now calls it in-process rather than
# shelling out to `cms-deepeval`.
from cms.cli.deepeval_launcher import export_env
from cms.config.logging_config import setup_logging

logger = logging.getLogger("cms.cli.evalset")

EVAL_DIR = Path("tests/evals/data")
DEFAULT_GOLDENS = EVAL_DIR / "goldens.json"


def _build(args: argparse.Namespace) -> int:
    from cms.evals.corpus import materialize_corpus

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="cms-evals-") as tmp:
            index = materialize_corpus(Path(tmp))
            print(f"{len(index)} document(s) materialised — nothing generated\n")
            for name, doc in index.items():
                size = doc.path.stat().st_size
                print(
                    f"  {doc.corpus:6} {name:38} "
                    f"({doc.department or 'company-wide'}) — {size:,} bytes"
                )
        return 0

    from cms.evals.build import build_goldens

    export_env()
    records = build_goldens(args.out)

    corpora: dict[str, int] = {}
    for record in records:
        corpus = record["additional_metadata"]["corpus"]
        corpora[corpus] = corpora.get(corpus, 0) + 1

    print(f"\nWrote {len(records)} golden(s) to {args.out}")
    print("  " + ", ".join(f"{count} {corpus}" for corpus, count in sorted(corpora.items())))
    print(f"\nNext: cms-evalset verify --goldens {args.out}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    from cms.evals.verify import verify_goldens

    result = verify_goldens(args.goldens)
    print(f"\n{result.summary()}")
    # A golden whose own source is unreachable will fail the retriever evals
    # regardless of the retriever, so this is worth a non-zero exit.
    return 1 if result.missing else 0


def main() -> int:
    setup_logging()

    # Seed-corpus text is arbitrary UTF-8 (₹, em dashes, accents); Windows
    # terminals default stdout to the system codepage (cp1252), which cannot
    # encode it — see the identical fix in cli/retrieve.py.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Build and verify the eval golden dataset."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser(
        "build",
        help="Generate the golden dataset from the seed corpus in one pass.",
    )
    build.add_argument("--out", type=Path, default=DEFAULT_GOLDENS)
    build.add_argument(
        "--dry-run",
        action="store_true",
        help="Materialise the corpus and print it; generate nothing, spend nothing.",
    )
    build.set_defaults(func=_build)

    verify = subparsers.add_parser(
        "verify",
        help="Check each golden's own source is retrievable for its own input "
        "(needs Qdrant; free).",
    )
    verify.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    verify.set_defaults(func=_verify)

    args = parser.parse_args()

    try:
        return args.func(args)
    except Exception:
        logger.exception("cms-evalset %s failed", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
