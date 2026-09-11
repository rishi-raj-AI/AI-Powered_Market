"""Explicit platform capabilities for privileged backend operations.

Roles remain coarse identity categories.  Capabilities are the authorization
boundary: adding a new role grants nothing until it is mapped here.  The
existing ``is_super_admin`` flag is deliberately treated as a scoped authority
tier on an ADMIN user, not as a business-rule bypass.
"""

from __future__ import annotations

import enum

from app.models.user import User, UserRole


class Capability(str, enum.Enum):
    USER_READ = "user.read"
    USER_MANAGE = "user.manage"
    ADMIN_MANAGE = "admin.manage"
    MERCHANT_READ = "merchant.read"
    MERCHANT_MANAGE = "merchant.manage"
    CATALOG_MANAGE = "catalog.manage"
    GEOGRAPHY_MANAGE = "geography.manage"
    ORDER_READ = "order.read"
    ORDER_OPERATIONS = "order.operations"
    RIDER_READ = "rider.read"
    RIDER_OPERATIONS = "rider.operations"
    SUPPORT_MANAGE = "support.manage"
    MEDIA_MODERATE = "media.moderate"
    NOTIFICATION_OPERATIONS = "notification.operations"
    PAYMENT_READ = "payment.read"
    REFUND_READ = "refund.read"
    REFUND_WRITE = "refund.write"
    SETTLEMENT_READ = "settlement.read"
    SETTLEMENT_WRITE = "settlement.write"
    DELIVERY_FINANCIAL_WRITE = "delivery_financial.write"
    AUDIT_READ = "audit.read"


# Normal administrators operate the marketplace but receive no capability
# which directly or indirectly writes money state.
ADMIN_CAPABILITIES = frozenset(
    {
        Capability.USER_READ,
        Capability.USER_MANAGE,
        Capability.MERCHANT_READ,
        Capability.MERCHANT_MANAGE,
        Capability.CATALOG_MANAGE,
        Capability.GEOGRAPHY_MANAGE,
        Capability.ORDER_READ,
        Capability.ORDER_OPERATIONS,
        Capability.RIDER_READ,
        Capability.RIDER_OPERATIONS,
        Capability.SUPPORT_MANAGE,
        Capability.MEDIA_MODERATE,
        Capability.NOTIFICATION_OPERATIONS,
        Capability.PAYMENT_READ,
        Capability.REFUND_READ,
        Capability.SETTLEMENT_READ,
    }
)

SUPER_ADMIN_CAPABILITIES = ADMIN_CAPABILITIES | frozenset(
    {
        Capability.ADMIN_MANAGE,
        Capability.REFUND_WRITE,
        Capability.SETTLEMENT_WRITE,
        Capability.DELIVERY_FINANCIAL_WRITE,
        Capability.AUDIT_READ,
    }
)


def capabilities_for(user: User) -> frozenset[Capability]:
    """Resolve capabilities deny-by-default for every unmapped role/state."""
    if user.role != UserRole.ADMIN:
        return frozenset()
    return SUPER_ADMIN_CAPABILITIES if user.is_super_admin else ADMIN_CAPABILITIES


def has_capability(user: User, capability: Capability) -> bool:
    return capability in capabilities_for(user)
