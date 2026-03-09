"""Model access: chat generation, embeddings, and versioned prompts.

Chat and embedding models are kept in separate subpackages on purpose. They have
independent lifecycles — swapping the generation model is a prompt-and-eval
change, swapping the embedding model invalidates every vector already stored —
so nothing here should let one drag the other along.
"""
