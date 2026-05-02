"""Contracts for the generation stage: what a `[n]` marker in a draft points at."""

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class Citation(_Base):
    """One numbered chunk in the generated context block.

    `marker` is the `[n]` the model is told to cite with, so a draft's `[3]` and
    `citations[2]` describe the same chunk. `section` is the heading breadcrumb
    the chunker prepends to every policy chunk — it is what makes a citation
    readable ("Warranty > 2.3 Charging Circuit") instead of a bare id.
    """

    marker: int
    doc_id: str
    chunk_id: str
    title: str
    section: str
