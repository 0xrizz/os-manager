"""Memory management and zRAM optimization subsystem."""
from os_manager.memory.zram import (
    CANONICAL_ZRAM_CONF,
    CANONICAL_ZRAM_DEVICE,
    CANONICAL_ZRAM_GENERATOR_PKG,
    CONFLICTING_ZRAM_SERVICES,
    ConflictingServiceStatus,
    ZramAuditReport,
    audit_zram_system,
    generate_canonical_zram_conf,
    remediate_zram_conflicts,
    unmask_zram_service,
)

__all__ = [
    "CANONICAL_ZRAM_CONF",
    "CANONICAL_ZRAM_DEVICE",
    "CANONICAL_ZRAM_GENERATOR_PKG",
    "CONFLICTING_ZRAM_SERVICES",
    "ConflictingServiceStatus",
    "ZramAuditReport",
    "audit_zram_system",
    "generate_canonical_zram_conf",
    "remediate_zram_conflicts",
    "unmask_zram_service",
]
