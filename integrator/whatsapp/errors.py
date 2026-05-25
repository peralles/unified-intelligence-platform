from __future__ import annotations


class WhatsAppError(Exception):
    """Base WhatsApp integration error."""


class WhatsAppNotConnectedError(WhatsAppError):
    """Session not paired or worker disconnected."""


class WhatsAppApiError(WhatsAppError):
    """Worker or neonize operation failed."""
