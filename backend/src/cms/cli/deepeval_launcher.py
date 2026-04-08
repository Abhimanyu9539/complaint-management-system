"""Run the `deepeval` CLI with this project's TLS and env bootstrap applied.

`deepeval generate` is its own process, so it never imports `cms` and never
gets the truststore injection in `cms/config/__init__.py`. On this machine
that is fatal, not cosmetic: the TLS-intercepting proxy's root CA is in the
Windows certificate store but not in certifi's bundle, so every OpenAI call
the synthesizer makes dies with

    [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate

This launcher is a one-line fix in the right place — import `cms.config` for
its side effects, then hand `sys.argv` straight to deepeval's own Typer app.
Flags, help text and exit codes are deepeval's; nothing is wrapped or
reinterpreted, so `cms-deepeval generate ...` and `deepeval generate ...` are
the same command with the same options.

It also loads `backend/.env` into the environment on the way through. deepeval
reads `OPENAI_API_KEY` from the process environment and knows nothing about
pydantic-settings, so without this the key has to be exported by hand before
every run.

    cms-deepeval generate --method contexts --contexts-file ./tests/evals/data/contexts.json ...
"""

import logging
import os
import sys

# Imported for its side effects: truststore injection + LangSmith env export.
# Must precede the deepeval import, which builds HTTPS clients of its own.
import cms.config  # noqa: F401
from cms.config.logging_config import setup_logging
from cms.config.settings import resolve_env_file

logger = logging.getLogger("cms.cli.deepeval")

# Everything deepeval needs from the environment. Deliberately a small
# allowlist rather than the whole .env: this hands variables to a third-party
# process, and Supabase secrets have no business being in its environment.
_EXPORTED_KEYS = ("OPENAI_API_KEY", "DEEPEVAL_TELEMETRY_OPT_OUT")


def export_env() -> None:
    """Copy the keys deepeval needs from `.env` into `os.environ`.

    Never overwrites a variable already set: an operator who exported a
    different key for one run means it, and silently preferring the file would
    make that impossible to do.
    """
    env_file = resolve_env_file()
    if env_file is None:
        logger.info("No .env file found; relying on the process environment")
        return

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        logger.exception("Could not read %s; relying on the process environment", env_file)
        return

    for line in lines:
        key, separator, value = line.strip().partition("=")
        key = key.strip()
        if not separator or key.startswith("#") or key not in _EXPORTED_KEYS:
            continue
        if os.environ.get(key):
            logger.debug("%s already set in the environment; leaving it alone", key)
            continue
        os.environ[key] = value.strip().strip('"').strip("'")
        logger.info("Exported %s from %s", key, env_file)

    # deepeval reports anonymous usage stats unless told not to. Default it off
    # rather than requiring every developer to remember the .env line.
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


def main() -> int:
    setup_logging()

    # The synthesizer echoes corpus text (₹, em dashes) as it works; Windows
    # terminals default stdout to cp1252 — see the same fix in cli/retrieve.py.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        export_env()
        from deepeval.cli.main import app
    except Exception:
        logger.exception("Could not bootstrap the deepeval CLI")
        return 1

    # Typer raises SystemExit to report its own status; let it through
    # unchanged so `cms-deepeval` exits exactly as `deepeval` would.
    app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
