# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Top-level package initializer.

Provides a package-level ``logger`` configured with a NullHandler so
that consumers can opt-in to logging configuration.
"""

from importlib.metadata import PackageNotFoundError, version

from quantilica.core.logging import get_logger

try:
    __version__ = version("sidra-fetcher")
except PackageNotFoundError:
    __version__ = "0.0.0"

logger = get_logger(__name__)
