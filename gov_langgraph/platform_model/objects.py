"""
platform_model.objects — Step 2 Frozen Objects

V1 minimum governed object model.
All 7 first-class objects defined in Step 2.

Objects defined here are the source of truth.
LangGraph, Harness, and PMO surface all reference these — not replace them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Literal


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProjectStatus(str, Enum):
    # V1.6 lifecycle states
    DRAFT = "draft"  # project created, no prerequisites tracked yet
    INTAKE_SUBMITTED = "intake_submitted"  # prerequisites tracked, not all submitted
    PRE_KICKOFF_REVIEW = "pre_kickoff_review"  # all 6 artifacts submitted, awaiting review
    KICKOFF_READY = "kickoff_ready"  # review complete, Maverick recommends kickoff
    REVIEW_REJECTED = "review_rejected"  # review failed, revisions needed
    # V1.5 retained states
    ACTIVE = "active"  # execution in progress
    ON_HOLD = "on_hold"
    CLOSED = "closed"
    SHUTDOWN = "shutdown"


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    READY_FOR_ACCEPTANCE = "ready_for_acceptance"
    REVISION_REQUESTED = "revision_requested"
    DONE = "done"
    CANCELLED = "cancelled"


class HandoffStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class GateDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    HELD = "held"
    STOPPED = "stopped"
    RETURNED = "returned"


# ---------------------------------------------------------------------------
# Role Enum — V1 Authority Model
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """
    V1 role enum — authority/system identity only.

    Roles are governance labels for permission enforcement.
    Full agent definitions (Soul, Memory, Scope) are defined
    separately when agents are actually embodied.

    Resolved: ALEX, NOVA, JARVIS, MAVERICK, VIPER_BA, VIPER_SA,
    VIPER_DEV, VIPER_QA
    """

    ALEX = "alex"
    NOVA = "nova"
    JARVIS = "jarvis"
    MAVERICK = "maverick"
    VIPER_BA = "viper_ba"
    VIPER_SA = "viper_sa"
    VIPER_DEV = "viper_dev"
    VIPER_QA = "viper_qa"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Sprint 2R: Pre-Kickoff Review Model
# ---------------------------------------------------------------------------

class ReviewStatus(str, Enum):
    """Status for a single reviewer's pre-kickoff review."""
    PENDING = "pending"
    APPROVED = "approved"
    REVISION_NEEDED = "revision_needed"


class MaverickRecommendationStatus(str, Enum):
    """Maverick's consolidated recommendation after reviewing all BA/SA/QA outcomes."""
    PENDING = "pending"
    RECOMMEND_KICKOFF = "recommend_kickoff"
    RECOMMEND_REVISION = "recommend_revision"


class KickoffDecisionStatus(str, Enum):
    """Alex's final kickoff decision."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ReviewRecord:
    """
    Tracks a single reviewer's pre-kickoff review state.
    Used during the V1.6 PRE_KICKOFF_REVIEW phase.
    """
    status: ReviewStatus = ReviewStatus.PENDING
    requested_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    note: str = ""


@dataclass
class MaverickRecommendation:
    """
    Maverick's consolidated recommendation after reviewing all BA/SA/QA outcomes.
    Separate from individual reviewer status — Maverick synthesizes, doesn't replace.
    """
    status: MaverickRecommendationStatus = MaverickRecommendationStatus.PENDING
    recommended_at: Optional[datetime] = None
    note: str = ""


@dataclass
class KickoffDecision:
    """
    Alex's final kickoff decision.
    Distinct from Maverick recommendation — Alex is the final authority.
    """
    status: KickoffDecisionStatus = KickoffDecisionStatus.PENDING
    decided_at: Optional[datetime] = None
    note: str = ""

@dataclass
class Project:
    """
    Top-level governed delivery container.
    Anchors workflow context, status visibility, and PMO tracking.

    Step 2 fields: project_id, project_name, project_goal, domain_type,
    workflow_template_id, project_status, created_at, project_summary,
    project_owner
    """

    project_name: str
    project_goal: str
    domain_type: str
    project_owner: str
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_template_id: Optional[str] = None
    project_status: ProjectStatus = ProjectStatus.ACTIVE
    project_summary: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Optional fields
    closed_at: Optional[datetime] = None

    # V1.5: artifact registry — artifact_id -> Artifact
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    # V1.5: latest acceptance package for this project
    acceptance_package: Optional[AcceptancePackage] = None
    # V1.5: advisory signals — advisory_id -> AdvisorySignal
    advisories: dict[str, AdvisorySignal] = field(default_factory=dict)
    # V1.5: blockers — blocker_id -> Blocker
    blockers: dict[str, Blocker] = field(default_factory=dict)

    # V1.6: Structured intake fields
    # Required at creation: intake_summary, intake_deliverable, intake_business_context
    # Arch is optional at intake (downstream delivery artifact)
    intake_complete: bool = False
    intake_summary: str = ""
    intake_deliverable: str = ""
    intake_business_context: str = ""
    # V1.6: Output package — added at acceptance/closure
    output_package: dict = field(default_factory=dict)

    # V1.6: Prerequisite package — artifact_type -> PrereqArtifact
    # Initialized empty at project creation (DRAFT state)
    prerequisite_artifacts: dict[str, PrereqArtifact] = field(default_factory=dict)
    # Timestamp when all 6 prerequisite artifacts were submitted
    prerequisite_submitted_at: Optional[datetime] = None


    # Sprint 2R: Pre-kickoff review (V1.6)
    ba_review: ReviewRecord = field(default_factory=ReviewRecord)
    sa_review: ReviewRecord = field(default_factory=ReviewRecord)
    qa_review: ReviewRecord = field(default_factory=ReviewRecord)
    maverick_recommendation: MaverickRecommendation = field(default_factory=MaverickRecommendation)
    kickoff_decision: Optional[KickoffDecision] = None
    # --- Prerequisite package helpers ---

    def initialize_prerequisites(self) -> None:
        """
        Initialize all 6 prerequisite artifacts in NOT submitted state.
        Called when project is created.
        """
        self.prerequisite_artifacts = {}
        for at in ArtifactType.all():
            self.prerequisite_artifacts[at.value] = PrereqArtifact(artifact_type=at)

    def submit_prerequisite(
        self,
        artifact_type: str,
        content_preview: str = "",
        producer: str = "",
    ) -> None:
        """
        Mark one prerequisite artifact as submitted.
        Updates project_status: DRAFT -> INTAKE_SUBMITTED -> PRE_KICKOFF_REVIEW
        """
        if artifact_type not in self.prerequisite_artifacts:
            raise ValueError(f"Unknown artifact type: {artifact_type}")

        pa = self.prerequisite_artifacts[artifact_type]
        pa.artifact_id = str(uuid.uuid4())
        pa.submitted = True
        pa.content_preview = content_preview
        pa.producer = producer
        pa.submitted_at = datetime.utcnow()

        # Auto-transition status based on submission count
        submitted_count = sum(1 for p in self.prerequisite_artifacts.values() if p.submitted)
        if submitted_count == 1:
            self.project_status = ProjectStatus.INTAKE_SUBMITTED
        if submitted_count == 6:
            self.project_status = ProjectStatus.PRE_KICKOFF_REVIEW
            self.prerequisite_submitted_at = datetime.utcnow()

    def get_prerequisite_package(self) -> dict:
        """
        Return all 6 prerequisite artifacts with their submission state.
        """
        return {
            at.value: {
                "artifact_type": pa.artifact_type.value,
                "artifact_id": pa.artifact_id,
                "submitted": pa.submitted,
                "content_preview": pa.content_preview,
                "producer": pa.producer,
                "submitted_at": pa.submitted_at.isoformat() if pa.submitted_at else None,
            }
            for at, pa in (
                (ArtifactType(at_str), self.prerequisite_artifacts[at_str])
                for at_str in self.prerequisite_artifacts
            )
        }

    def is_prerequisite_complete(self) -> bool:
        """Return True if all 6 prerequisite artifacts are submitted."""
        return all(pa.submitted for pa in self.prerequisite_artifacts.values())

    def build_output_package(self) -> dict:
        """
        Build and store the output package from delivered artifacts.
        Called when acceptance is approved.
        Returns the output_package dict.
        """
        type_map = self.get_artifacts_by_type()
        artifacts = []
        for at in ArtifactType.all():
            if at in type_map and not type_map[at].is_empty():
                art = type_map[at]
                artifacts.append({
                    "artifact_type": at.value,
                    "display_name": at.display_name,
                    "content": art.content,
                    "produced_by": art.produced_by,
                    "produced_at": art.produced_at.isoformat() if art.produced_at else None,
                })
        artifact_types_present = {a["artifact_type"] for a in artifacts}
        is_complete = all(at.value in artifact_types_present for at in ArtifactType.all())
        self.output_package = {
            "package_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat(),
            "is_complete": is_complete,
            "artifacts": artifacts,
        }
        return self.output_package

    def get_output_package(self) -> dict | None:
        """Return the output package if one has been built."""
        return self.output_package if self.output_package else None

    def validate_intake(self) -> bool:
        """
        Returns True if all required intake fields are present.
        Required: intake_summary, intake_deliverable, intake_business_context
        Arch is optional at intake.
        """
        return (
            bool(self.intake_summary and self.intake_summary.strip())
            and bool(self.intake_deliverable and self.intake_deliverable.strip())
            and bool(self.intake_business_context and self.intake_business_context.strip())
        )

    def complete_intake(self) -> None:
        """
        Marks intake as complete if all required fields are present.
        Raises ValueError if required fields are missing.
        """
        if not self.validate_intake():
            missing = []
            if not self.intake_summary.strip():
                missing.append("intake_summary")
            if not self.intake_deliverable.strip():
                missing.append("intake_deliverable")
            if not self.intake_business_context.strip():
                missing.append("intake_business_context")
            raise ValueError(f"Cannot complete intake — missing required fields: {', '.join(missing)}")
        self.intake_complete = True

    def __post_init__(self):
        if not self.project_name:
            raise ValueError("project_name is required")
        if not self.project_goal:
            raise ValueError("project_goal is required")

    def close(self) -> None:
        self.project_status = ProjectStatus.CLOSED
        self.closed_at = datetime.utcnow()

    def get_artifact(self, artifact_type: ArtifactType) -> Optional[Artifact]:
        """Get artifact by type for this project."""
        for artifact in self.artifacts.values():
            if artifact.artifact_type == artifact_type:
                return artifact
        return None

    def add_artifact(self, artifact: Artifact) -> None:
        """Add or replace an artifact for this project."""
        self.artifacts[artifact.artifact_id] = artifact

    def get_artifacts_by_type(self) -> dict[ArtifactType, Artifact]:
        """Return artifacts keyed by type."""
        result: dict[ArtifactType, Artifact] = {}
        for artifact in self.artifacts.values():
            result[artifact.artifact_type] = artifact
        return result

    def is_artifact_complete(self) -> bool:
        """All 6 required artifacts are non-empty."""
        type_map = self.get_artifacts_by_type()
        return all(
            at in type_map and not type_map[at].is_empty()
            for at in ArtifactType.all()
        )

    def get_missing_artifacts(self) -> list[ArtifactType]:
        """Return list of missing or empty artifact types."""
        type_map = self.get_artifacts_by_type()
        return [
            at for at in ArtifactType.all()
            if at not in type_map or type_map[at].is_empty()
        ]

    # --- Advisory helpers ---

    def add_advisory(self, advisory: AdvisorySignal) -> None:
        """Add an advisory signal to this project."""
        self.advisories[advisory.advisory_id] = advisory

    def get_active_advisories(self) -> list[AdvisorySignal]:
        """Return unacknowledged advisory signals, newest first."""
        return sorted(
            [a for a in self.advisories.values() if not a.acknowledged],
            key=lambda a: a.created_at,
            reverse=True,
        )

    def get_advisories_by_type(self, advisory_type: AdvisoryType) -> list[AdvisorySignal]:
        """Return all advisories of a given type."""
        return [
            a for a in self.advisories.values()
            if a.advisory_type == advisory_type and not a.acknowledged
        ]

    # --- Blocker helpers ---

    def add_blocker(self, blocker: Blocker) -> None:
        """Add a blocker to this project."""
        self.blockers[blocker.blocker_id] = blocker

    def get_active_blockers(self) -> list[Blocker]:
        """Return unresolved blockers."""
        return [b for b in self.blockers.values() if not b.is_resolved()]

    def get_blockers_for_task(self, task_id: str) -> list[Blocker]:
        """Return unresolved blockers for a specific task."""
        return [
            b for b in self.blockers.values()
            if b.task_id == task_id and not b.is_resolved()
        ]


# ---------------------------------------------------------------------------
# TaskState — separate from WorkItem per Step 2
# ---------------------------------------------------------------------------



    # --- Sprint 2R: Pre-kickoff Review Helpers ---

    def request_review(self, reviewer: Literal["ba", "sa", "qa"]) -> None:
        """Mark a review as requested. Sets requested_at timestamp."""
        record: ReviewRecord = getattr(self, f"{reviewer}_review")
        record.requested_at = datetime.utcnow()
        record.status = ReviewStatus.PENDING

    def record_review_outcome(
        self,
        reviewer: Literal["ba", "sa", "qa"],
        outcome: ReviewStatus,
        note: str = "",
    ) -> None:
        """Record a reviewer's outcome (APPROVED or REVISION_NEEDED)."""
        record: ReviewRecord = getattr(self, f"{reviewer}_review")
        record.status = outcome
        record.decided_at = datetime.utcnow()
        record.note = note

    def get_review_status(self) -> dict:
        """Return full review status as dict."""
        return {
            "ba": {
                "status": self.ba_review.status.value,
                "requested_at": self.ba_review.requested_at.isoformat() if self.ba_review.requested_at else None,
                "decided_at": self.ba_review.decided_at.isoformat() if self.ba_review.decided_at else None,
                "note": self.ba_review.note,
            },
            "sa": {
                "status": self.sa_review.status.value,
                "requested_at": self.sa_review.requested_at.isoformat() if self.sa_review.requested_at else None,
                "decided_at": self.sa_review.decided_at.isoformat() if self.sa_review.decided_at else None,
                "note": self.sa_review.note,
            },
            "qa": {
                "status": self.qa_review.status.value,
                "requested_at": self.qa_review.requested_at.isoformat() if self.qa_review.requested_at else None,
                "decided_at": self.qa_review.decided_at.isoformat() if self.qa_review.decided_at else None,
                "note": self.qa_review.note,
            },
            "maverick_recommendation": {
                "status": self.maverick_recommendation.status.value,
                "recommended_at": self.maverick_recommendation.recommended_at.isoformat() if self.maverick_recommendation.recommended_at else None,
                "note": self.maverick_recommendation.note,
            },
        }

    def is_review_complete(self) -> bool:
        """All 3 reviewers have decided (approved or revision_needed)."""
        return (
            self.ba_review.status != ReviewStatus.PENDING
            and self.sa_review.status != ReviewStatus.PENDING
            and self.qa_review.status != ReviewStatus.PENDING
        )

    def any_revision_needed(self) -> bool:
        """Any reviewer marked REVISION_NEEDED?"""
        return (
            self.ba_review.status == ReviewStatus.REVISION_NEEDED
            or self.sa_review.status == ReviewStatus.REVISION_NEEDED
            or self.qa_review.status == ReviewStatus.REVISION_NEEDED
        )

    def can_recommend_kickoff(self) -> bool:
        """Maverick may recommend kickoff only if all reviews complete AND none need revision."""
        return self.is_review_complete() and not self.any_revision_needed()

    def recommend_kickoff(
        self,
        recommendation: MaverickRecommendationStatus,
        note: str = "",
    ) -> None:
        """Maverick records a kickoff recommendation (RECOMMEND_KICKOFF or RECOMMEND_REVISION)."""
        self.maverick_recommendation.status = recommendation
        self.maverick_recommendation.recommended_at = datetime.utcnow()
        self.maverick_recommendation.note = note
        # Update project_status to match the recommendation
        if recommendation == MaverickRecommendationStatus.RECOMMEND_KICKOFF:
            self.project_status = ProjectStatus.KICKOFF_READY
        elif recommendation == MaverickRecommendationStatus.RECOMMEND_REVISION:
            self.project_status = ProjectStatus.REVIEW_REJECTED

    def decide_kickoff(
        self,
        decision: KickoffDecisionStatus,
        note: str = "",
    ) -> None:
        """Alex records final kickoff decision (APPROVED or REJECTED)."""
        self.kickoff_decision = KickoffDecision(
            status=decision,
            decided_at=datetime.utcnow(),
            note=note,
        )

@dataclass
class TaskState:
    """
    Current actionable operational condition of a WorkItem.
    Separate from the task definition itself (Step 2 requirement).

    Step 2 fields: task_id, current_stage, state_status, current_owner,
    current_blocker, next_expected_action, last_updated_at
    """

    task_id: str
    current_stage: str  # BA | SA | DEV | QA (Step 2 resolved stages)
    state_status: TaskStatus = TaskStatus.BACKLOG
    current_owner: Optional[str] = None
    current_blocker: Optional[str] = None
    next_expected_action: Optional[str] = None
    last_updated_at: datetime = field(default_factory=datetime.utcnow)

    def advance_stage(self, next_stage: str) -> None:
        """Advance to next stage. Does NOT validate — caller must validate first."""
        self.current_stage = next_stage
        self.last_updated_at = datetime.utcnow()

    def block(self, reason: str) -> None:
        self.current_blocker = reason
        self.state_status = TaskStatus.BLOCKED
        self.last_updated_at = datetime.utcnow()

    def unblock(self) -> None:
        self.current_blocker = None
        if self.state_status == TaskStatus.BLOCKED:
            self.state_status = TaskStatus.IN_PROGRESS
        self.last_updated_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# WorkItem
# ---------------------------------------------------------------------------


@dataclass
class WorkItem:
    """
    Minimum governed delivery unit.
    Step 2 keeps Task/WorkItem as one merged object.

    Step 2 fields: task_id, project_id, task_title, task_description,
    current_owner, dependency_task_ids, expected_deliverable, workflow_id,
    current_stage, task_status, handoff_target, priority
    """

    task_title: str
    project_id: str
    task_description: str = ""
    workflow_id: Optional[str] = None
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_owner: Optional[str] = None
    dependency_task_ids: list[str] = field(default_factory=list)
    expected_deliverable: Optional[str] = None
    current_stage: str = "BA"  # Default start stage
    task_status: TaskStatus = TaskStatus.BACKLOG
    handoff_target: Optional[str] = None
    priority: int = 0  # Higher = more urgent
    created_at: datetime = field(default_factory=datetime.utcnow)

    # V1 does NOT include: task_workflow_status, task_completion_percentage,
    # actual_hours, estimated_hours — these are deferred

    def __post_init__(self):
        if not self.task_title:
            raise ValueError("task_title is required")
        if not self.project_id:
            raise ValueError("project_id is required")

    def assign(self, owner: str) -> None:
        self.current_owner = owner

    def complete(self) -> None:
        self.task_status = TaskStatus.DONE


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@dataclass
class Workflow:
    """
    Reusable delivery path that governs how a WorkItem progresses through
    software delivery stages.

    Step 2 fields: workflow_id, workflow_name, domain_type, stage_list,
    allowed_transitions, stage_role_map, default_handoff_points,
    default_gate_points
    """

    workflow_name: str
    domain_type: str
    stage_list: list[str]  # e.g. ["BA", "SA", "DEV", "QA"]
    allowed_transitions: dict[str, list[str]]  # from_stage -> [to_stages]
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stage_role_map: dict[str, list[str]] = field(default_factory=dict)  # stage -> [roles]
    default_handoff_points: list[str] = field(default_factory=list)
    default_gate_points: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.workflow_name:
            raise ValueError("workflow_name is required")
        if not self.stage_list:
            raise ValueError("stage_list is required — at least one stage")
        # stage_role_map defaults: if a stage has no explicit role map, allow all
        for stage in self.stage_list:
            if stage not in self.stage_role_map:
                self.stage_role_map[stage] = [r.value for r in Role]

    def get_valid_next_stages(self, from_stage: str) -> list[str]:
        """Return list of valid target stages from a given stage."""
        return self.allowed_transitions.get(from_stage, [])

    def is_valid_transition(self, from_stage: str, to_stage: str) -> bool:
        return to_stage in self.get_valid_next_stages(from_stage)


# ---------------------------------------------------------------------------
# Handoff
# ---------------------------------------------------------------------------


@dataclass
class Handoff:
    """
    Formal governed transfer record of a task from one stage/owner to another,
    with a concrete deliverable reference.

    Step 2 fields: handoff_id, task_id, from_stage, to_stage, from_owner,
    to_owner, deliverable_reference, handoff_note, handoff_status, created_at
    """

    task_id: str
    from_stage: str
    to_stage: str
    from_owner: str
    to_owner: str
    deliverable_reference: Optional[str] = None
    handoff_note: str = ""
    handoff_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    handoff_status: HandoffStatus = HandoffStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)

    def accept(self) -> None:
        self.handoff_status = HandoffStatus.ACCEPTED

    def reject(self, reason: str = "") -> None:
        self.handoff_status = HandoffStatus.REJECTED
        if reason:
            self.handoff_note = reason


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


@dataclass
class Gate:
    """
    Formal decision/control object that determines whether a task may proceed,
    return, hold, or stop at a workflow boundary.

    Step 2 fields: gate_id, task_id, stage, gate_type, decision,
    decision_by, decision_note, decided_at
    """

    task_id: str
    stage: str
    gate_type: str  # e.g. "stage_advance", "handoff_approve"
    decision: Optional[GateDecision] = None
    decision_by: Optional[str] = None
    decision_note: str = ""
    gate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decided_at: Optional[datetime] = None

    def decide(self, decision: GateDecision, decided_by: str, note: str = "") -> None:
        self.decision = decision
        self.decision_by = decided_by
        self.decision_note = note
        self.decided_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------


class ArtifactType(str, Enum):
    """6 mandatory artifacts required for V1.5 project completion."""

    SCOPE = "scope"  # Alex defines on project creation
    SPEC = "spec"  # BA agent outputs after BA stage
    ARCH = "arch"  # SA agent outputs after SA stage
    TESTCASE = "testcase"  # QA prep outputs before QA stage
    TESTREPORT = "testreport"  # Alex UAT results after QA
    GUIDELINE = "guideline"  # Maverick drafts after project reaches COMPLETE

    @classmethod
    def all(cls) -> list["ArtifactType"]:
        return [cls.SCOPE, cls.SPEC, cls.ARCH, cls.TESTCASE, cls.TESTREPORT, cls.GUIDELINE]

    @property
    def display_name(self) -> str:
        return {
            "scope": "Scope",
            "spec": "Specification",
            "arch": "Architecture",
            "testcase": "Test Case",
            "testreport": "Test Report",
            "guideline": "Guideline",
        }[self.value]

    @property
    def generated_by(self) -> str:
        return {
            "scope": "Alex",
            "spec": "BA Agent",
            "arch": "SA Agent",
            "testcase": "QA Agent",
            "testreport": "Alex (UAT)",
            "guideline": "Maverick",
        }[self.value]

    @property
    def stage_hint(self) -> str:
        return {
            "scope": "Project Creation",
            "spec": "After BA",
            "arch": "After SA",
            "testcase": "Before QA",
            "testreport": "After QA",
            "guideline": "On Completion",
        }[self.value]


@dataclass
class PrereqArtifact:
    """
    Tracks a single prerequisite artifact's submission state.
    Used during the V1.6 intake/pre-kickoff phase.
    """
    artifact_type: ArtifactType
    artifact_id: Optional[str] = None  # assigned when submitted, used for view/download
    submitted: bool = False
    content_preview: str = ""
    producer: str = ""
    submitted_at: Optional[datetime] = None


@dataclass
class Artifact:
    """
    A named, typed output artifact produced during project delivery.
    One artifact exists per ArtifactType per project.
    """

    artifact_type: ArtifactType
    project_id: str
    content: str = ""
    file_path: Optional[str] = None
    produced_by: str = ""
    produced_at: datetime = field(default_factory=datetime.utcnow)
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def is_empty(self) -> bool:
        return not self.content and not self.file_path


@dataclass
class AcceptancePackage:
    """
    Formal acceptance package presented to Alex when a task reaches
    READY_FOR_ACCEPTANCE.
    """

    task_id: str
    project_id: str
    artifacts: dict[ArtifactType, Artifact] = field(default_factory=dict)
    verification_notes: str = ""
    approval_signatures: dict[str, str] = field(default_factory=dict)  # role -> signature
    acceptance_decision: Optional[GateDecision] = None
    decision_by: Optional[str] = None
    decision_note: str = ""
    decided_at: Optional[datetime] = None
    package_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    def is_complete(self) -> bool:
        """All 6 required artifacts are non-empty."""
        return all(
            not artifact.is_empty()
            for artifact in self.artifacts.values()
        )

    def get_missing_artifacts(self) -> list[ArtifactType]:
        """Return list of artifact types that are missing or empty."""
        return [
            at for at in ArtifactType.all()
            if at not in self.artifacts or self.artifacts[at].is_empty()
        ]

    def approve(self, decided_by: str, note: str = "") -> None:
        self.acceptance_decision = GateDecision.APPROVED
        self.decision_by = decided_by
        self.decision_note = note
        self.decided_at = datetime.utcnow()

    def reject(self, decided_by: str, note: str) -> None:
        self.acceptance_decision = GateDecision.REJECTED
        self.decision_by = decided_by
        self.decision_note = note
        self.decided_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Advisory Signal (Sprint 4)
# ---------------------------------------------------------------------------


class AdvisoryType(str, Enum):
    """Advisory signal types — informational only, non-blocking."""

    RISK = "risk"
    SCHEDULE = "schedule"
    STAGE = "stage"
    SUMMARY = "summary"
    BLOCKER = "blocker"

    @classmethod
    def all(cls) -> list["AdvisoryType"]:
        return [cls.RISK, cls.SCHEDULE, cls.STAGE, cls.SUMMARY, cls.BLOCKER]


@dataclass
class AdvisorySignal:
    """
    Non-blocking advisory signal surfaced from Maverick's coordination.
    Advisory signals are informational only — they inform humans but do not
    halt or alter pipeline state.
    """

    advisory_type: AdvisoryType
    project_id: str
    message: str
    severity: str = "info"
    task_id: Optional[str] = None
    stage: Optional[str] = None
    actor: str = "maverick"
    advisory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False

    def ack(self) -> None:
        self.acknowledged = True


# ---------------------------------------------------------------------------
# Blocker (Sprint 4)
# ---------------------------------------------------------------------------


class BlockerSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Blocker:
    """
    Explicit blocker record for a task — surfaced by Maverick.
    Blockers are detected conditions, not governance decisions.
    They do not change task state — they surface it for human review.
    """

    task_id: str
    project_id: str
    reason: str
    blocker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: BlockerSeverity = BlockerSeverity.MEDIUM
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def resolve(self, resolved_by: str) -> None:
        self.resolved_at = datetime.utcnow()
        self.resolved_by = resolved_by

    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    def age_hours(self) -> float:
        delta = datetime.utcnow() - self.detected_at
        return delta.total_seconds() / 3600


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


@dataclass
class Event:
    """
    Traceable governance-relevant record of meaningful action, change,
    or condition in project delivery.

    Step 2 fields: event_id, project_id, task_id, event_type, actor,
    event_summary, related_stage, timestamp

    Note: task_id may be empty for project-level events.
    """

    project_id: str
    event_type: str  # e.g. "task_created", "stage_advanced", "gate_approved"
    event_summary: str
    actor: str  # Role or agent name that triggered the event
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None
    related_stage: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
