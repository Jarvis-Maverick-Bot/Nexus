"""
platform_model.exceptions — V1 Exception Hierarchy

Base: PlatformException
├── AuthorityViolation    — action denied by authority rules
├── InvalidTransitionError — stage transition not in allowed_transitions
├── StageNotFoundError    — target stage not in workflow
├── ObjectNotFoundError   — referenced governance object does not exist
└── ValidationError       — field validation failure

All exceptions are operator-facing / human-readable by default.
Developer-only detail is kept in exception messages.
"""


class PlatformException(Exception):
    """
    Base exception for all platform errors.
    All messages are safe to show to operators.
    """

    def __init__(self, message: str, detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class AuthorityViolation(PlatformException):
    """
    Raised when an action is not authorized.
    """

    def __init__(
        self,
        action: str,
        actor_role: str,
        reason: str = "",
        task_id: str | None = None,
    ):
        self.action = action
        self.actor_role = actor_role
        self.reason = reason
        self.task_id = task_id
        parts = [f"Action '{action}' denied for role '{actor_role}'"]
        if reason:
            parts.append(reason)
        if task_id:
            parts.append(f"Task: {task_id}")
        message = ": ".join(parts)
        super().__init__(message, detail=reason)


class InvalidTransitionError(PlatformException):
    """
    Raised when a stage transition is not in the workflow's allowed_transitions.
    """

    def __init__(self, from_stage: str, to_stage: str, valid_stages: list[str] | None = None):
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.valid_stages = valid_stages or []
        msg = f"Cannot transition from '{from_stage}' to '{to_stage}'"
        if valid_stages:
            msg += f". Valid next stages: {valid_stages}"
        super().__init__(msg)


class StageNotFoundError(PlatformException):
    """
    Raised when a stage name is not found in the workflow.
    """

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"Stage '{stage}' not found in this workflow")


class ObjectNotFoundError(PlatformException):
    """
    Raised when a governance object (Project, WorkItem, etc.) does not exist.
    """

    def __init__(self, object_type: str, object_id: str):
        self.object_type = object_type
        self.object_id = object_id
        super().__init__(f"{object_type} '{object_id}' not found")


class ValidationError(PlatformException):
    """
    Raised when field validation fails on a governance object.
    """

    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"Validation failed for '{field}': {reason}")
