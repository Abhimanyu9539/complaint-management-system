"""All app settings. Each group lives in its own module; `Settings` combines them into one flat class."""

import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from cms.config.settings.chat import ChatSettings
from cms.config.settings.email import EmailSettings
from cms.config.settings.flywheel import FlywheelSettings
from cms.config.settings.generation import GenerationSettings
from cms.config.settings.guardrails import GuardrailSettings
from cms.config.settings.llm import LLMSettings
from cms.config.settings.messages import MessageSettings
from cms.config.settings.prompts import PromptSettings
from cms.config.settings.retrieval import RetrievalSettings
from cms.config.settings.server import ServerSettings

logger = logging.getLogger(__name__)

ENV_FILE_VAR = "CMS_ENV_FILE"


def resolve_env_file() -> Path | None:
    """Locate the `.env` file without depending on the working directory.

    The package is installed, so entrypoints can be launched from anywhere —
    a relative `".env"` would silently resolve to nothing and the required
    fields below would fail with a confusing "field required" instead of
    "your config wasn't found". Tried in order:

    1. `$CMS_ENV_FILE`, an explicit override for containers and CI.
    2. A `.env` in the cwd or any parent — covers `backend/` and any
       subdirectory of it, which is how this is run in development.
    3. The source-tree `backend/.env`, relative to this file. Only resolves
       for an editable install; a wheel in site-packages has no such parent,
       which is correct — deployments pass real environment variables.

    Returning None is not an error: real env vars still populate Settings, and
    that is the expected path in a deployed container.
    """
    override = os.environ.get(ENV_FILE_VAR)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path
        # Explicitly asked for and not there — worth a warning rather than a
        # silent fallback that loads a *different* file than the one requested.
        logger.warning("%s=%s does not exist; ignoring it", ENV_FILE_VAR, override)

    try:
        cwd = Path.cwd().resolve()
        for directory in (cwd, *cwd.parents):
            candidate = directory / ".env"
            if candidate.is_file():
                return candidate
    except OSError:
        # A deleted or unreadable cwd must not stop us reaching the fallback.
        logger.exception("Could not search upward from the working directory")

    # src/cms/config/settings/__init__.py -> backend/
    source_tree = Path(__file__).resolve().parents[4] / ".env"
    if source_tree.is_file():
        return source_tree

    logger.info("No .env file found; relying on process environment variables")
    return None


class Settings(
    BaseSettings,
    LLMSettings,
    RetrievalSettings,
    PromptSettings,
    GenerationSettings,
    GuardrailSettings,
    EmailSettings,
    ChatSettings,
    FlywheelSettings,
    ServerSettings,
    MessageSettings,
):
    """Single source of truth for all environment configuration.

    Fields stay flat (`settings.smtp_host`, env `SMTP_HOST`), whichever group module they live in.
    Required fields (no default) fail fast at startup if missing, rather than
    surfacing as a confusing error on the first request that needs them.
    """

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """The process-wide Settings, built once.

    `_env_file` is passed per-call rather than pinned in `model_config` so the
    file lookup reflects the working directory at first use. Environment
    variables still take precedence over anything in the file.
    """
    return Settings(_env_file=resolve_env_file())
