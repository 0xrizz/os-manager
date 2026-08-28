"""Memory management and zRAM optimization subsystem."""
from os_manager.memory.zram import (
    CONFLICTING_ZRAM_SERVICES,
    ConflictingServiceStatus,
    ZramAuditReport,
    audit_zram_system,
)

__all__ = [
    "CONFLICTING_ZRAM_SERVICES",
    "ConflictingServiceStatus",
    "ZramAuditReport",
    "audit_zram_system",
]
