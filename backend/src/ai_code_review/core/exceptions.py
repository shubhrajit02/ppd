"""Errors safe for callers to handle without a traceback."""


class ReviewError(Exception):
    """A review could not be completed."""


class InputError(ReviewError):
    """Invalid or inaccessible review input."""


class ProviderError(ReviewError):
    """An optional model provider could not return usable findings."""
