# LLM Review Contract — V0.1

**Date:** 2026-04-21
**Status:** DRAFT — pending Nova + Alex approval before implementation
**Collab ID prefix:** foundation-*

---

## 1. Architecture

```
review_executor.py (业务逻辑层)
    │
    ├── assembles review_packet (metadata + evidence_packer)
    │
    ▼
llm_adapter.py (模型接入抽象层)
    │
    ├── provider: configurable (minimax / openai / anthropic / ...)
    ├── model: configurable
    ├── api_key: from auth-profiles (not hardcoded)
    ├── retry / timeout: adapter-level policy
    │
    ▼
MiniMax / OpenAI / ... (模型 provider)
```

**原则：**
- review_executor.py 永远不直接 import urllib / httpx / boto3
- llm_adapter.py 永远不包含业务逻辑
- 输入结构由 contract 定义，adapter 负责把结构序列化成 provider 接受的格式

---

## 2. Review Packet Structure (Layer A: Metadata)

Every review_request carries this metadata into the reasoning layer:

| Field | Source | Required |
|-------|--------|---------|
| collab_id | envelope.collab_id | YES |
| workflow | payload.workflow | YES |
| stage | payload.stage | YES |
| review_round | state.review_round (1-indexed) | YES |
| max_review_rounds | state.max_review_rounds (from config) | YES |
| artifact_type | payload.artifact_type | YES |
| review_scope | payload.review_scope | YES |
| artifact_path | payload.artifact_path (sharefolder path) | YES |
| from_ | envelope.from_ | YES |

---

## 3. Evidence Packet Structure (Layer B: Content)

Evidence is NOT always full text. Evidence packer decides what to include.

### Evidence Packer Logic

```
IF draft_length < 5000 chars:
    evidence = draft_full_text
ELSE:
    evidence = draft_summary + key_sections

IF doctrine_length < 8000 chars per file:
    doctrine_evidence = full_text
ELSE:
    doctrine_evidence = structured_excerpt (relevant sections only)
```

**Evidence packet fields:**

| Field | Content | Rationale |
|-------|---------|-----------|
| draft_text | Full or summarized draft | Must — this is what we judge |
| baseline_excerpt | Relevant baseline sections | Avoid token overflow |
| scope_excerpt | Relevant scope sections | Avoid token overflow |
| prd_excerpt | Relevant PRD requirements | Avoid token overflow |
| review_context | Round info + termination stakes | Tell LLM what's at risk |

---

## 4. Rule Layer → LLM Layer → Runtime Layer分工

### Rule Layer (pre-LLM guard)

Runs BEFORE LLM call. Catches obvious failures fast.

| Rule | Condition | Action |
|------|-----------|--------|
| draft_exists | artifact_path not accessible | Return revision_required |
| draft_not_empty | draft content < 50 chars | Return blocked |
| max_rounds_exceeded | review_round > max_review_rounds | Return blocked + set termination_reason |
| round_limit | review_round == max_review_rounds | Set termination_warning in context |

### LLM Layer (judgment producer)

Only called if rule layer passes.

**System prompt contract:**
- Role: strict V2.0 Foundation review judge
- Output format: VERDICT line + NOTES line ONLY
- Allowed verdicts: APPROVED / REVISION_REQUIRED / BLOCKED
- Must provide specific, actionable feedback for REVISION_REQUIRED and BLOCKED

**Runtime enforces:**
- Verdict must be one of the three allowed values
- NOTES must be non-empty for REVISION_REQUIRED and BLOCKED
- If LLM output doesn't parse: treated as BLOCKED with raw output in notes

### Runtime Validation Layer (post-LLM gate)

| Check | If fails | Action |
|-------|---------|--------|
| verdict in allowed_results | True | Accept |
| notes non-empty (if revision_required or blocked) | False | Rewrite notes = "Verdict issued but notes empty — treated as blocking" |
| notes length > 20 chars | False | Rewrite notes = raw_output[:200] |

---

## 5. Structured Output Schema

LLM must output exactly:

```
VERDICT: [APPROVED|REVISION_REQUIRED|BLOCKED]
NOTES: [specific, actionable feedback — what Nova must fix]
```

**Parsing rules:**
- Extract first line starting with "VERDICT:"
- Extract first line starting with "NOTES:"
- Everything after NOTES: is the feedback content
- If either line missing → runtime rewrite

---

## 6. max_review_rounds Configuration Source

| Source | Priority | Location |
|--------|---------|---------|
| collab_config.json | 1 (highest) | `max_review_rounds` field |
| state CollabState | 2 | `max_review_rounds` attribute |
| Default | 3 | Hardcoded fallback |

**Behavior when max reached:**
```
IF review_round > max_review_rounds:
    status = 'blocked'
    termination_reason = 'max_review_rounds_exceeded'
    pending_action = ''
    NO automatic retry
    Telegram notification to Alex: "Review blocked — max rounds exceeded"
```

---

## 7. State Fields (CollabState)

```
review_round: int       # 0 = not started, 1 = first review, ...
max_review_rounds: int  # from config, default 3
termination_reason: str # '' | 'max_review_rounds_exceeded' | ...
last_review_result: str # approved | revision_required | blocked
last_review_notes: str  # raw notes from LLM
```

---

## 8. review_executor.py Responsibilities (after refactor)

1. Assemble review_packet (Layer A metadata)
2. Call evidence_packer to build Layer B
3. Run rule layer checks (fast-fail)
4. If rule layer passes → call llm_adapter.judge()
5. Parse LLM output → enforce structured schema
6. Run runtime validation
7. Return DomainResult (never raw LLM output)
8. Write judgment artifact to governance/docs/

---

## 9. llm_adapter.py Interface

```python
class LLMAdapter:
    def __init__(self, provider: str, model: str, api_key: str):
        ...

    def judge(self, review_packet: dict, evidence_packet: dict) -> LLMOutput:
        """
        review_packet: Layer A metadata
        evidence_packet: Layer B content
        Returns: LLMOutput(verdict: str, notes: str, raw: str)
        """
        ...
```

**Provider config (collab_config.json):**
```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M2.7",
    "api_key_profile": "minimax:global",
    "timeout_seconds": 60,
    "max_retries": 2
  }
}
```

---

## 10. Decision Table: What Happens When

| Event | Rule Layer | LLM Layer | Runtime | State |
|-------|-----------|-----------|---------|-------|
| draft not found | revision_required | skip | accept | last_review_result=revision_required |
| draft empty | blocked | skip | accept | last_review_result=blocked |
| round > max | blocked | skip | accept | status=blocked, termination_reason=... |
| rule passes, LLM returns APPROVED | pass | APPROVED | accept | last_review_result=approved |
| rule passes, LLM returns REVISION_REQUIRED | pass | REVISION_REQUIRED | accept + validate notes | last_review_result=revision_required |
| rule passes, LLM returns BLOCKED | pass | BLOCKED | accept | last_review_result=blocked |
| rule passes, LLM returns garbage | pass | treated as BLOCKED | rewrite notes | last_review_result=blocked |
| LLM API error | treated as BLOCKED | skip | accept | last_review_result=blocked, notes=error |

---

## 11. Open Questions (need Nova + Alex decision)

1. **evidence_packer granularity** — at what token length do we switch from full to excerpt?
2. **API key storage** — read from auth-profiles.json at runtime, or pass via environment variable?
3. **Fallback provider** — if MiniMax fails, retry with different provider or fail fast?
4. **Judgment artifact** — write to shared drive (so Nova can read) or local only?
5. **Telegram notification trigger** — on every review_response, or only on final round / blocked?
