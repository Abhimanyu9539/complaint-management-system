"""Reranking, via OpenRouter.
"""

import logging
from collections.abc import Sequence
from copy import deepcopy

import httpx
from langchain_core.callbacks.manager import Callbacks
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor

from cms.schemas.rerank import RerankResponse

logger = logging.getLogger(__name__)

RERANK_PATH = "/rerank"


class OpenRouterRerank(BaseDocumentCompressor):
    """Document compressor backed by OpenRouter's rerank endpoint."""

    api_key: str
    model: str
    base_url: str
    top_n: int | None = None
    timeout: float = 30.0

    def _request(self, documents: Sequence[Document], query: str) -> tuple[str, dict, dict]:
        """The url, headers and json body for one rerank call.

        `top_n` is OpenRouter's spelling of what the Voyage SDK calls `top_k`.
        `return_documents` is left off: we already hold the originals and match
        results back by `index`, so echoing the text back is paid-for noise.
        """
        payload: dict = {
            "model": self.model,
            "query": query,
            "documents": [document.page_content for document in documents],
        }
        if self.top_n is not None:
            payload["top_n"] = self.top_n

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return f"{self.base_url.rstrip('/')}{RERANK_PATH}", headers, payload

    def _to_documents(
        self, body: dict, documents: Sequence[Document]
    ) -> list[Document]:
        """Results back onto their source documents, best-first.

        Metadata matches what `VoyageAIRerank` writes — `relevance_score` and
        `total_tokens` — so callers cannot tell the two providers apart.
        """
        response = RerankResponse.model_validate(body)
        total_tokens = response.usage.total_tokens if response.usage else None

        compressed = []
        for result in response.results:
            # A bad index means the response does not describe the request we
            # sent; failing here beats silently returning the wrong chunk.
            if not 0 <= result.index < len(documents):
                raise ValueError(
                    f"OpenRouter returned index {result.index} for a pool of "
                    f"{len(documents)} document(s)"
                )
            source = documents[result.index]
            document = Document(source.page_content, metadata=deepcopy(source.metadata))
            document.metadata["relevance_score"] = result.relevance_score
            document.metadata["total_tokens"] = total_tokens
            compressed.append(document)
        return compressed

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        """Rerank `documents` against `query`, best-first."""
        if not documents:
            return []

        url, headers, payload = self._request(documents, query)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception:
            logger.exception(
                "OpenRouter rerank failed (model=%s, documents=%d)",
                self.model,
                len(documents),
            )
            raise

        return self._to_documents(body, documents)

    async def acompress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        """Async `compress_documents`.

        The client is built per call rather than cached on the instance: an
        `AsyncClient` binds its connection pool to the loop that created it, and
        the eval suite runs `asyncio.run` once per golden against a reranker
        that is cached for the whole process.
        """
        if not documents:
            return []

        url, headers, payload = self._request(documents, query)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception:
            logger.exception(
                "OpenRouter rerank failed (model=%s, documents=%d)",
                self.model,
                len(documents),
            )
            raise

        return self._to_documents(body, documents)
