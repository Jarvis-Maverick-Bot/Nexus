# Governance LangGraph - Technical Specification

**Version:** V0.1
**Date:** 2026-04-05
**Author:** Alex + Jarvis

---

## 1. Overview

**Purpose:** Multi-agent governance system using LangGraph for orchestration and OpenClaw as the execution platform.

**Scope:** Implement Maverick (PMO), Viper (Delivery), and Nova (Audit) as LangGraph nodes with governance rules.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     OPENCLAW                             │
│  Telegram入口 / Session管理 / Tool系统 / Agent循环        │
├─────────────────────────────────────────────────────────┤
│                   LANGGRAPH                              │
│  状态机 / 节点编排 / Checkpoint持久化 / 流程控制        │
├─────────────────────────────────────────────────────────┤
│                 GOVERNING LAYER                         │
│  Maverick (PMO)  ←→  Viper (BA/SA/DEV/QA)  ←→  Nova (Audit) │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Core Components

### 3.1 State Definition

```python
class GovernanceState(TypedDict):
    # 任务信息
    task_id: str
    task_description: str
    current_stage: str  # "BA" | "SA" | "DEV" | "QA" | "DONE"
    
    # APQ 授权
    apq_authorized: bool
    authorization_source: str | None
    
    # 治理状态
    pending_halt: bool
    halt_reason: str | None
    governance_violations: list[str]
    
    # 执行状态
    prd_content: str | None
    spec_content: str | None
    deliverable_content: str | None
    qa_report: str | None
    
    # 审计
    audit_log: list[dict]
    nova_findings: list[dict]
```

### 3.2 Nodes

| Node | Role | Responsibilities |
|------|------|------------------|
| `maverick` | PMO Coordinator | APQ check, route/halt, stage authorization |
| `viper_ba` | Business Analyst | Create PRD document |
| `viper_sa` | Systems Analyst | Create SPEC document |
| `viper_dev` | Developer | Create deliverable artifact |
| `viper_qa` | Quality Assurance | Verify and approve/reject |
| `nova` | Auditor | Review governance compliance, file issues |

### 3.3 Edges

```
maverick → [authorize?] → viper_ba → viper_sa → viper_dev → viper_qa → nova → END
                ↓
            [halt] → END
```

### 3.4 Governance Rules

| Rule | Trigger | Action |
|------|---------|--------|
| `apq_required` | Task not in approved queue | Halt, require authorization |
| `stage_boundary` | Unauthorized stage transition | Reject, return to Maverick |
| `role_boundary` | Agent out of role | Hard stop |
| `halt_on_violation` | Any governance violation | Log and halt |

---

## 4. File Structure

```
governance-langgraph/
├── SPEC.md                    # 本文档
├── requirements.txt            # Python 依赖
├── pyproject.toml             # 项目配置
├── langgraph/
│   ├── __init__.py
│   ├── state.py              # GovernanceState 定义
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── maverick.py       # PMO 协调节点
│   │   ├── viper_ba.py       # BA 节点
│   │   ├── viper_sa.py       # SA 节点
│   │   ├── viper_dev.py      # DEV 节点
│   │   ├── viper_qa.py       # QA 节点
│   │   └── nova.py           # 审计节点
│   └── edges.py              # 流程边定义
├── governance/
│   ├── __init__.py
│   ├── apq.py               # APQ 规则引擎
│   ├── handoff.py           # 交接协议
│   └── audit.py             # 审计工具
├── api/
│   ├── __init__.py
│   └── app.py               # FastAPI 接口
├── openclaw_integration/
│   ├── __init__.py
│   └── tools.py             # OpenClaw Tool 定义
├── tests/
│   └── test_pipeline.py     # 集成测试
└── main.py                  # 入口脚本
```

---

## 5. Dependencies

```
langgraph >= 0.2.0
langchain-core >= 0.3.0
langchain-openai >= 0.2.0
fastapi >= 0.115.0
uvicorn >= 0.32.0
pydantic >= 2.0
```

---

## 6. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/task` | POST | 提交新任务 |
| `/task/{id}` | GET | 获取任务状态 |
| `/task/{id}/halt` | POST | 终止任务 |
| `/health` | GET | 健康检查 |

---

## 7. Integration with OpenClaw

### 7.1 As OpenClaw Tool

```python
# OpenClaw Tool 定义
@tool
def run_governance_pipeline(task: str) -> str:
    """运行治理管道"""
    # 调用 LangGraph
    pass
```

### 7.2 As OpenClaw Agent

```python
# 自定义 Agent 使用 LangGraph
class GovernanceAgent:
    # 使用 LangGraph 作为推理引擎
    pass
```

---

## 8. Acceptance Criteria

| Criteria | Description |
|----------|-------------|
| AC1 | LangGraph pipeline runs BA→SA→DEV→QA stages |
| AC2 | APQ check halts unauthorized tasks |
| AC3 | Each stage writes checkpoint to state |
| AC4 | Nova reviews and files findings |
| AC5 | OpenClaw can invoke pipeline as Tool |
| AC6 | All state persists across sessions |

---

## 9. Next Steps

1. [ ] 创建项目结构
2. [ ] 实现 GovernanceState
3. [ ] 实现 Maverick 节点 (APQ check)
4. [ ] 实现 Viper 节点 (BA/SA/DEV/QA)
5. [ ] 实现 Nova 节点 (审计)
6. [ ] 定义 Edges 和流程
7. [ ] 添加持久化
8. [ ] OpenClaw 集成
9. [ ] 测试

---

## 10. Notes

- 基于 LangGraph 的 checkpoint 机制实现状态持久化
- 使用 OpenAI API 作为 LLM 后端
- 未来可扩展到多 Agent 并行执行
