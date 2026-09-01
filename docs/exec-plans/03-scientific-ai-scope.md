# Phase 3 Scope — Scientific AI + Evaluation

**Status:** SCOPE ONLY — DO NOT EXECUTE AS A DETAILED PLAN YET.

必须在 Phase 2 真实完成后，根据 repo 和 handoff 重新规划。

## Goal

把 AI 放在科研判断节点，而不是把 Workspace 变成聊天应用。

路径：

```text
Selected Experiments
+ Measurements
+ Literature Evidence
      ↓
Scientific Analysis
      ↓
Finding
      ↓
Evidence Gate
      ↓
Human Review
  ┌───────────────┐
Accept  Reject  Needs Evidence
          ↓
       Bad Case
          ↓
      Evaluation
```

## P0 Capabilities

### 1. AI Analysis
输入必须显式：
- experiments
- measurements
- literature evidence

输出必须结构化。

### 2. Finding

字段：
- claim
- confidence
- supporting evidence
- contradicting evidence
- risks / limitations
- suggested next experiment

### 3. Evidence Gate

至少状态：
- supported
- partially_supported
- insufficient_evidence
- contradicted

AI 不得只给一个不可解释 confidence number。

### 4. Human Review

- Accept
- Reject
- Needs Evidence
- reviewer comment
- rejection reason taxonomy

### 5. Bad Case

Reject 可转换为 evaluation case：
- input context snapshot
- model output
- expected behaviour
- failure tags

### 6. Evaluation

Phase 3 planning 时评估是否直接接 Langfuse：
- traces
- datasets
- experiments
- scores

优先通过 API/SDK 使用，不复制 Langfuse codebase。

### 7. Optional LangGraph

只有真实 AI workflow 已出现清晰多节点、状态分支和重试需求时才引入。

禁止为关键词硬塞 multi-agent。

### 8. MCP

不属于 v0.1-demo P0。
如果 Phase 3 完成后需要让外部 Agent 访问 Workspace，再单独规划。

## Exit Criteria — v0.1-demo

完整演示必须跑通：

```text
Project
→ Experiment
→ Data
→ Compare
→ Evidence
→ AI Finding
→ Risk
→ Reject
→ Bad Case
→ Eval
→ Suggested Next Experiment
```

此时打 tag：

`v0.1-demo`
