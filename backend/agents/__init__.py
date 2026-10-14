"""The five Campus Customs roles. One file per agent; ROLES maps name -> RoleSpec."""

from agents import accounting, boss, customer_service, facilities, inventory
from agents.spec import RoleSpec

ROLES: dict[str, RoleSpec] = {
    m.SPEC.name: m.SPEC for m in (boss, inventory, accounting, facilities, customer_service)
}
