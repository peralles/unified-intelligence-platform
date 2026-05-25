"""WhatsApp local session (neonize worker subprocess)."""

from integrator.whatsapp.errors import (
    WhatsAppApiError,
    WhatsAppNotConnectedError,
)
from integrator.whatsapp.session import WhatsAppSession

__all__ = [
    "WhatsAppApiError",
    "WhatsAppNotConnectedError",
    "WhatsAppSession",
]
