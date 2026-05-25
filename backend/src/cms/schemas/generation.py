"""Contracts for the generation stage: what a `[n]` marker in a draft points at."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# Which corpus a citation's `doc_id` resolves in — cases and policies are separate tables.
DocType = Literal["policy", "case"]


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class Citation(_Base):
    """One numbered chunk in the generated context block.

    `marker` is the `[n]` the model is told to cite with, so a draft's `[3]` and
    `citations[2]` describe the same chunk. `section` is the heading breadcrumb
    the chunker prepends to every policy chunk — it is what makes a citation
    readable ("Warranty > 2.3 Charging Circuit") instead of a bare id.

    `snippet` is the chunk body the UI shows under a citation, so a reader can
    check the claim against the source without opening the document. It carries
    no weight inside the graph — nothing prompts or validates on it — which is
    why it defaults to empty rather than being required.
    """

    marker: int
    doc_id: str
    chunk_id: str
    title: str
    section: str
    snippet: str = ""
    doc_type: DocType = "policy"
