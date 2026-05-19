"""Reporters serialize lists of Issue into stable on-disk formats.

Each reporter is independent — no shared base class is needed for v1.
All reporters consume the same `list[Issue]` input.
"""
