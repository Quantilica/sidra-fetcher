# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Top-level package initializer.

Provides a package-level ``logger`` configured with a NullHandler so
that consumers can opt-in to logging configuration.
"""

import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
