"""Complaint Management System backend.

Deliberately empty of logic. The process bootstrap (OS trust store, LangSmith
env export) lives in `cms.config`, not here, because it must run before the
first HTTPS client is built and *every* module in this package reaches
configuration through `cms.config.settings` — importing this top-level package
alone is not a signal that anything is about to make a network call.
"""
