"""
maverick_spawner — Maverick PMO agent scheduling layer

Loads agent and workflow definitions from config/agents.yaml.
Provides flexible agent scheduling for V1.5 PMO operations.

Rule: Nothing hardcoded. All agent/workflow definitions live in config/agents.yaml.
"""

from __future__ import annotations

import os
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import sys

_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = os.environ.get(
    "MAVERICK_AGENTS_CONFIG",
    str(_ROOT / "config" / "agents.yaml")
)


@dataclass
class SpawnResult:
    ok: bool
    session_key: str | None = None
    status: str = ""  # "spawned" | "failed" | "no_agent" | "config_error"
    error: str | None = None


@dataclass
class AgentConfig:
    agent_id: str
    role: str
    stage: str
    description: str = ""


class MaverickSpawner:
    """
    Flexible agent scheduler — routes work to known agents based on context.

    Reads agent and workflow definitions from config/agents.yaml.
    Does NOT hardcode agent IDs or workflow sequences.

    V1.5: Uses one-shot spawn via sessions_spawn.
    V2.0: Can be extended to use persistent sessions if available.
    """

    def __init__(self, config_path: str | None = None):
        self._config_path = config_path or _CONFIG_PATH
        self._agents: dict[str, AgentConfig] = {}
        self._workflows: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _load_config(self) -> None:
        """Load agent and workflow definitions from YAML config."""
        if self._loaded:
            return

        config_file = Path(self._config_path)
        if not config_file.exists():
            # Fall back to empty config
            self._agents = {}
            self._workflows = {}
            self._loaded = True
            return

        with open(config_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        agents_raw = raw.get("agents", {})
        for role, cfg in agents_raw.items():
            self._agents[role] = AgentConfig(
                agent_id=cfg.get("agent_id", ""),
                role=cfg.get("role", role),
                stage=cfg.get("stage", ""),
                description=cfg.get("description", ""),
            )

        self._workflows = raw.get("workflows", {})
        self._loaded = True

    @property
    def agents(self) -> dict[str, AgentConfig]:
        self._load_config()
        return self._agents

    @property
    def workflows(self) -> dict[str, dict[str, Any]]:
        self._load_config()
        return self._workflows

    def list_roles(self) -> list[str]:
        """Return all known agent roles from config."""
        return list(self.agents.keys())

    def get_agent(self, role: str) -> AgentConfig | None:
        """Return config for a specific role, or None if unknown."""
        return self.agents.get(role)

    def list_workflows(self) -> list[str]:
        """Return all known workflow names from config."""
        return list(self.workflows.keys())

    def get_workflow(self, name: str) -> dict[str, Any] | None:
        """Return workflow definition, or None if unknown."""
        return self.workflows.get(name)

    def _build_context(
        self,
        project_name: str,
        project_id: str,
        task_title: str,
        task_id: str,
        current_stage: str,
    ) -> str:
        """Build a structured rehydration context string for spawned agent."""
        agent_cfg = self.get_agent(current_stage)
        role_desc = agent_cfg.role if agent_cfg else current_stage

        return (
            f"You are acting as {role_desc} for project '{project_name}' "
            f"(ID: {project_id}). "
            f"Task: '{task_title}'. "
            f"Stage: {current_stage}. "
            f"Workitem ID: {task_id}. "
            f"When done, write your output to the Harness evidence store."
        )

    def schedule(
        self,
        project_name: str,
        project_id: str,
        task_title: str,
        task_id: str,
        current_stage: str,
        role: str | None = None,
    ) -> SpawnResult:
        """
        Schedule a known agent for a task.

        Args:
            project_name: Human-readable project name
            project_id: UUID of the project
            task_title: Title of the task
            task_id: UUID of the task
            current_stage: Current pipeline stage (BA, SA, DEV, QA)
            role: Optional explicit role override. If None, uses current_stage as role key.

        Returns:
            SpawnResult with ok=True if spawned, ok=False with error if failed.
        """
        self._load_config()

        # Resolve role — default to current_stage
        if role is None:
            role = current_stage.lower()

        agent_cfg = self.get_agent(role)
        if agent_cfg is None:
            return SpawnResult(
                ok=False,
                session_key=None,
                status="no_agent",
                error=f"Unknown role: '{role}'. Known roles: {self.list_roles()}",
            )

        context = self._build_context(
            project_name=project_name,
            project_id=project_id,
            task_title=task_title,
            task_id=task_id,
            current_stage=current_stage,
        )

        return self._spawn(agent_cfg.agent_id, context)

    def _spawn(self, agent_id: str, task: str) -> SpawnResult:
        """Call sessions_spawn. Returns SpawnResult."""
        try:
            from openclaw import sessions_spawn

            result = sessions_spawn(
                task=task,
                runtime="subagent",
                agentId=agent_id,
                mode="run",
            )

            return SpawnResult(
                ok=True,
                session_key=result.get("sessionKey"),
                status="spawned",
            )
        except ImportError:
            return SpawnResult(
                ok=False,
                session_key=None,
                status="failed",
                error="sessions_spawn not available in this environment",
            )
        except Exception as e:
            return SpawnResult(
                ok=False,
                session_key=None,
                status="failed",
                error=str(e),
            )
