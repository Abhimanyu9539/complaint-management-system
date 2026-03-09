"""Extract: read source documents and hand back plain dicts / text.

One module per corpus, because the two corpora arrive in genuinely different
shapes — a case is a structured Postgres row, a policy is a markdown file with
frontmatter — and merging them would mean a function that dispatches on a type
string for every field it touches.
"""
