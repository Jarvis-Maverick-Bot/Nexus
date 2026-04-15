"""
governance/collaborators/registry.py
V1.9 Sprint 1, Task T4.3
Collaborator registry.

Maps named collaborator role -> module implementation.
Used by routing rules to determine ownership and deliver items.

Architecture reference: Arch Doc §19 — bounded persistent collaborator capability
"""

from typing import Dict, Type, Optional, List

from .base import CollaboratorBase


class CollaboratorRegistry:
    """
    Registry of active collaborators.

    Maps role names to instantiated collaborator objects.
    Used by routing to determine which collaborator owns an inbox.
    """

    def __init__(self):
        self._collaborators: Dict[str, CollaboratorBase] = {}
        self._role_to_class: Dict[str, Type[CollaboratorBase]] = {}

    def register(
        self,
        role_name: str,
        collaborator: CollaboratorBase,
    ) -> None:
        """
        Register a collaborator instance by role name.

        Args:
            role_name: stable identity (e.g., "planner", "tdd")
            collaborator: instantiated CollaboratorBase subclass
        """
        if not isinstance(collaborator, CollaboratorBase):
            raise TypeError(f"Collaborator must be CollaboratorBase instance, got {type(collaborator)}")
        self._collaborators[role_name] = collaborator

    def register_class(
        self,
        role_name: str,
        collaborator_class: Type[CollaboratorBase],
    ) -> None:
        """
        Register a collaborator class and instantiate it lazily.

        Args:
            role_name: stable identity
            collaborator_class: CollaboratorBase subclass
        """
        if not issubclass(collaborator_class, CollaboratorBase):
            raise TypeError(f"Must be CollaboratorBase subclass, got {collaborator_class}")
        self._role_to_class[role_name] = collaborator_class

    def get(self, role_name: str) -> Optional[CollaboratorBase]:
        """
        Get collaborator by role name.

        Lazily instantiates from class if only class is registered.

        Args:
            role_name: the collaborator role to retrieve

        Returns:
            CollaboratorBase instance or None if not found
        """
        if role_name in self._collaborators:
            return self._collaborators[role_name]
        if role_name in self._role_to_class:
            cls = self._role_to_class[role_name]
            instance = cls()
            self._collaborators[role_name] = instance
            return instance
        return None

    def list_roles(self) -> List[str]:
        """Return all registered role names."""
        roles = set(self._collaborators.keys())
        roles.update(self._role_to_class.keys())
        return sorted(roles)

    def get_status(self, role_name: str) -> Optional[Dict]:
        """
        Get status for a specific collaborator.

        Returns None if not registered.
        """
        collab = self.get(role_name)
        if collab is None:
            return None
        return collab.get_status()

    def all_status(self) -> List[Dict]:
        """Return status for all registered collaborators."""
        statuses = []
        for role in self.list_roles():
            status = self.get_status(role)
            if status:
                statuses.append(status)
        return statuses

    def is_registered(self, role_name: str) -> bool:
        """Returns True if role is registered (instance or class)."""
        return role_name in self._collaborators or role_name in self._role_to_class

    def unregister(self, role_name: str) -> bool:
        """
        Remove a collaborator from the registry.

        Returns True if removed, False if wasn't registered.
        """
        if role_name in self._collaborators:
            del self._collaborators[role_name]
        if role_name in self._role_to_class:
            del self._role_to_class[role_name]
        return role_name not in self._collaborators and role_name not in self._role_to_class


# Default registry instance
_default_registry: Optional[CollaboratorRegistry] = None


def get_registry() -> CollaboratorRegistry:
    """Get the default registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = CollaboratorRegistry()
        # Auto-register initial proof-case collaborators
        from .planner import get_planner
        from .tdd import get_tdd
        _default_registry.register("planner", get_planner())
        _default_registry.register("tdd", get_tdd())
    return _default_registry