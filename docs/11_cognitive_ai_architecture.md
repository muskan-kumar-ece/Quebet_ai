# 11 — Cognitive AI Architecture
## QUEBET AI Electronics Engineer Platform
> Document Version: 1.0.0 | Classification: Core Architecture | Status: Active
> *The document that transforms QUEBET from an AI-assisted SaaS into a cognitive engineering system.*

---

## PREAMBLE — WHY THIS DOCUMENT EXISTS

Every LLM-powered product in 2024 routes a user message to a model and returns a response. That is not intelligence — that is autocomplete at scale. QUEBET AI's Cognitive Architecture is the system that sits between user intent and model output, and does the work that separates a trusted engineering tool from a sophisticated text generator.

The central problem in electronics engineering AI is not raw capability — it is **reasoning reliability under domain constraints**. A circuit has physics. Physics has laws. Laws have mathematical consequences. When an AI recommends placing a 16V-rated capacitor on an 18V rail, the error is not ambiguous — it is objectively wrong. A cognitive architecture must be able to:

1. **Decompose** a complex engineering request into atomic reasoning units
2. **Execute** each unit with the right tool, model, and verification chain
3. **Verify** each intermediate conclusion before building on it
4. **Aggregate** partial results with calibrated confidence
5. **Reflect** on its own reasoning chain and self-correct before delivery
6. **Persist** engineering context across sessions to improve over time
7. **Escalate** when confidence is insufficient — to a more capable model, a deterministic engine, or a human

This document defines the complete cognitive architecture of QUEBET AI — how agents are structured, how they communicate, how memory flows between sessions, how the system reflects on its own outputs, and how autonomous debugging and design workflows execute without human intervention at every step.

---

## SECTION 1 — COGNITIVE ARCHITECTURE OVERVIEW

### 1.1 The Cognitive Stack

QUEBET AI's cognitive layer operates as a five-tier stack. Each tier has a defined responsibility, defined inputs, and defined outputs. No tier does work that belongs to another.

```
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 5: INTERFACE LAYER                                            │
│  User intent arrives here. Raw, ambiguous, engineering-laden.       │
│  Output: Normalized IntentPacket → Cognitive Planner                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 4: COGNITIVE PLANNER                                          │
│  Decomposes intent. Selects agent graph. Estimates token budget.    │
│  Output: ExecutionPlan → Task Dispatcher                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 3: SPECIALIZED AGENT LAYER                                    │
│  Domain agents execute atomic reasoning tasks in parallel or        │
│  sequence. Each agent owns one cognitive skill.                     │
│  Output: AgentResult[] → Confidence Aggregator                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 2: VERIFICATION & REFLECTION LAYER                            │
│  All agent outputs pass through verification before assembly.       │
│  Self-reflection loops catch contradictions and low-confidence      │
│  reasoning chains before they reach the user.                       │
│  Output: VerifiedResult → Response Assembler                        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 1: MEMORY & LEARNING LAYER                                    │
│  Every interaction updates three memory systems. The system         │
│  learns user patterns, improves retrieval, and accumulates          │
│  engineering knowledge that persists across sessions.               │
│  Output: Updated MemoryState (async, non-blocking)                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 What Changes With a Cognitive Architecture

The contrast between a naive LLM call and QUEBET's cognitive processing:

| Dimension | Naive LLM Call | QUEBET Cognitive Architecture |
|---|---|---|
| Reasoning unit | Single prompt → single response | Intent → plan → multi-agent execution → verification → assembly |
| Error detection | None — output is taken as-is | Multi-stage: schema, physics, rules, cross-model consensus |
| Failure handling | Returns error string to user | Retries with different agent, escalates model, requests more input |
| Context | Current message only | Session memory + long-term engineering memory + RAG corpus |
| Confidence | Implicit (model doesn't know) | Explicit score computed across validation stages |
| Traceability | None | Full reasoning trace: which agent ran, what it returned, how it was verified |
| Self-correction | None | Reflection agent identifies contradictions, triggers re-analysis |
| Improvement | Static — same quality forever | Memory layer accumulates correct reasoning, improves future sessions |

---

## SECTION 2 — AGENT HIERARCHY

### 2.1 Agent Classification

QUEBET AI uses three agent tiers. The classification determines autonomy level, tool access, and escalation authority.

```
TIER A — ORCHESTRATION AGENTS (1 active per request)
├── CognitivePlannerAgent       ← Master orchestrator. Plans everything.
└── ReflectionAgent             ← Post-execution auditor. Challenges everything.

TIER B — DOMAIN SPECIALIST AGENTS (selected per task)
├── CircuitDesignAgent          ← Generates circuits, schematics, BOMs
├── FailureAnalysisAgent        ← Identifies failure modes, risk scoring
├── ThermalAnalysisAgent        ← Physics-based thermal calculations
├── EMIAnalysisAgent            ← Electromagnetic interference analysis
├── RepairDiagnosisAgent        ← Fault diagnosis, repair procedures
├── ComponentIntelligenceAgent  ← Component identification, alternatives
├── SimulationAgent             ← SPICE execution, result interpretation
├── LearningAgent               ← Adaptive tutoring, concept explanation
└── KnowledgeRetrievalAgent     ← RAG retrieval, graph traversal

TIER C — VALIDATION AGENTS (run on every output)
├── SchemaValidationAgent       ← JSON schema conformance check
├── EngineeringRuleAgent        ← Domain rule enforcement (physics, standards)
├── SafetyAuditorAgent          ← Safety constraint verification
└── ConfidenceAggregatorAgent   ← Computes final confidence score from all signals
```

### 2.2 Agent Base Contract

Every agent in QUEBET AI implements the `CognitiveAgent` abstract base class. This contract defines what it means to be an agent in this system:

```python
# services/cognitive/base_agent.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time

class AgentStatus(str, Enum):
    IDLE        = "idle"
    RUNNING     = "running"
    COMPLETED   = "completed"
    FAILED      = "failed"
    ESCALATED   = "escalated"  # Output confidence insufficient — escalated to stronger agent
    DEFERRED    = "deferred"   # Waiting for another agent's output

@dataclass
class AgentContext:
    """Everything an agent knows when it starts executing."""
    request_id: str
    user_id: str
    user_plan: str                          # "free" | "pro" | "enterprise"
    user_skill_level: str                   # "student" | "engineer" | "expert"
    session_memory: "SessionMemory"         # Current session context
    long_term_memory: "EngineeringMemory"   # User's persistent engineering history
    rag_context: str                        # Pre-retrieved RAG context from KnowledgeRetrievalAgent
    execution_plan: "ExecutionPlan"         # The plan this agent is executing within
    prior_agent_results: list["AgentResult"]  # Results from agents that ran before this one

@dataclass
class AgentResult:
    """Standardized output from any agent."""
    agent_id: str
    agent_type: str
    status: AgentStatus
    
    # Primary output
    output: dict                            # Structured, schema-validated output
    output_schema_version: str             # Which Pydantic schema validated this output
    
    # Reasoning trace (critical for explainability)
    reasoning_steps: list[str]             # Ordered list of reasoning steps taken
    tools_called: list["ToolCallRecord"]   # Every tool call with input/output
    models_consulted: list[str]            # Which LLM models were invoked
    
    # Confidence signals
    schema_valid: bool
    rules_passed: list[str]
    rules_failed: list[str]
    self_confidence: float                 # Model's own confidence estimate (0.0–1.0)
    computed_confidence: float             # QUEBET's computed confidence from all signals
    
    # Operational metadata
    execution_time_ms: int
    token_cost_usd: float
    retry_count: int
    
    # Escalation
    escalation_reason: Optional[str] = None
    requires_human_review: bool = False

class CognitiveAgent(ABC):
    """
    Base class for all QUEBET AI cognitive agents.
    
    Every agent:
    1. Receives a normalized context object
    2. Executes its specialized cognitive task
    3. Returns a standardized AgentResult
    4. Never calls another domain agent directly (only through the planner)
    5. Has a declared tool set it is authorized to use
    """
    
    AGENT_ID: str               # Unique identifier: "thermal_analysis_agent"
    AGENT_VERSION: str          # Semantic version: "v1.2.0"
    AUTHORIZED_TOOLS: list[str] # Tool names this agent may invoke
    MAX_RETRIES: int = 2
    TIMEOUT_SECONDS: int = 30
    
    @abstractmethod
    async def execute(self, task: "AgentTask", context: AgentContext) -> AgentResult:
        """
        Core execution logic. Must return AgentResult regardless of success or failure.
        Must never raise exceptions — capture them and return status=FAILED.
        """
        pass
    
    @abstractmethod
    def estimate_token_cost(self, task: "AgentTask") -> int:
        """
        Pre-execution token cost estimate. Used by Planner for budget management.
        Over-estimate by 20% — it is better to budget conservatively.
        """
        pass
    
    async def execute_with_retry(self, task: "AgentTask", context: AgentContext) -> AgentResult:
        """Retry wrapper — all agents use this, not execute() directly from orchestration."""
        for attempt in range(self.MAX_RETRIES + 1):
            start_time = time.monotonic()
            try:
                result = await self.execute(task, context)
                result.retry_count = attempt
                result.execution_time_ms = int((time.monotonic() - start_time) * 1000)
                
                if result.computed_confidence >= 0.6:
                    return result
                elif attempt < self.MAX_RETRIES:
                    # Low confidence — retry with adjusted temperature
                    task.temperature_override = max(0.0, task.temperature - 0.1 * attempt)
                    continue
                else:
                    result.status = AgentStatus.ESCALATED
                    result.escalation_reason = f"Confidence {result.computed_confidence:.2f} below threshold after {attempt+1} attempts"
                    return result
                    
            except Exception as e:
                if attempt == self.MAX_RETRIES:
                    return self._create_failure_result(str(e), attempt)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
    def _create_failure_result(self, error: str, attempts: int) -> AgentResult:
        return AgentResult(
            agent_id=self.AGENT_ID,
            agent_type=self.__class__.__name__,
            status=AgentStatus.FAILED,
            output={},
            output_schema_version="none",
            reasoning_steps=[f"Failed after {attempts+1} attempts: {error}"],
            tools_called=[],
            models_consulted=[],
            schema_valid=False,
            rules_passed=[],
            rules_failed=[f"AGENT_EXECUTION_FAILED: {error}"],
            self_confidence=0.0,
            computed_confidence=0.0,
            execution_time_ms=0,
            token_cost_usd=0.0,
            retry_count=attempts
        )
```

---

## SECTION 3 — COGNITIVE PLANNER AGENT

The `CognitivePlannerAgent` is the most critical component in the cognitive stack. It receives raw user intent and transforms it into a structured execution plan that other agents can follow. It does not perform domain analysis — it reasons about *how* to perform domain analysis.

### 3.1 Intent Normalization

Before planning begins, user input is normalized into an `IntentPacket` — a structured representation that separates what the user wants from how they described it:

```python
# services/cognitive/intent_normalizer.py

@dataclass
class IntentPacket:
    """Normalized representation of user engineering intent."""
    
    # Primary intent classification
    primary_intent: IntentType  # DESIGN | ANALYZE | TROUBLESHOOT | LEARN | IDENTIFY | OPTIMIZE
    
    # Extracted engineering entities
    components_mentioned: list[str]        # ["ESP32", "IRF540N", "100µF capacitor"]
    circuit_topology: Optional[str]        # "buck converter", "H-bridge", "amplifier"
    operating_conditions: dict             # {"voltage": "12V", "current": "2A", "temp": "40°C"}
    target_board: Optional[str]            # "Arduino Uno", "ESP32-WROOM", "STM32F4"
    
    # Constraint extraction
    explicit_constraints: list[str]        # User-stated constraints: "must fit in 50x50mm"
    implicit_constraints: list[str]        # Inferred: "student project" → "standard components only"
    
    # User context (from memory)
    inferred_skill_level: str
    likely_use_case: str                   # "student_lab", "product_prototype", "repair"
    
    # Ambiguity flags
    ambiguities: list[str]                 # Things the planner needs clarified
    requires_clarification: bool           # Should planner ask before executing?
    confidence_in_intent: float            # How confident is the normalizer? < 0.7 → ask

class IntentNormalizer:
    """
    Uses a lightweight model (fast, cheap) to extract structure from free text.
    Does not answer the engineering question — only classifies and extracts.
    """
    
    async def normalize(self, raw_input: str, context: AgentContext) -> IntentPacket:
        prompt = INTENT_NORMALIZATION_PROMPT.render(
            raw_input=raw_input,
            user_history_summary=context.long_term_memory.get_summary(),
            recent_topics=context.session_memory.recent_topics
        )
        
        # Use fast model for normalization — this is classification, not reasoning
        result = await self.fast_provider.complete(
            system=prompt,
            user=raw_input,
            temperature=0.0,        # Zero temperature — classification must be deterministic
            max_tokens=500          # Normalization output is compact
        )
        
        return IntentPacket(**json.loads(result))
```

### 3.2 Execution Plan Construction

Given a normalized intent, the planner builds an `ExecutionPlan` — a directed acyclic graph of agent tasks with dependencies, resource budgets, and parallelization strategy:

```python
# services/cognitive/planner_agent.py

@dataclass
class AgentTask:
    """A single unit of work in an execution plan."""
    task_id: str
    agent_type: str                         # Which agent class handles this
    task_description: str                   # What this task accomplishes
    input_schema: dict                      # What input this task requires
    depends_on: list[str]                   # task_ids that must complete before this runs
    can_run_parallel_with: list[str]        # task_ids that can run simultaneously
    priority: int                           # Execution priority (1=highest)
    token_budget: int                       # Maximum tokens this task may consume
    model_requirement: ModelRequirement     # FAST | STANDARD | POWERFUL | VISION
    temperature: float                      # Task-specific temperature
    timeout_seconds: int
    is_critical: bool                       # If True and fails, abort entire plan

@dataclass  
class ExecutionPlan:
    """Complete execution graph for a user request."""
    plan_id: str
    intent: IntentPacket
    tasks: list[AgentTask]
    execution_order: list[list[str]]        # Grouped by execution wave: [[t1,t2], [t3], [t4,t5]]
    estimated_total_tokens: int
    estimated_duration_seconds: float
    estimated_cost_usd: float
    requires_async: bool                    # If True, run as Celery job, not inline
    plan_rationale: str                     # Why was this plan chosen over alternatives?
    fallback_plan: Optional["ExecutionPlan"]  # Simpler plan if primary plan fails

class CognitivePlannerAgent(CognitiveAgent):
    AGENT_ID = "cognitive_planner"
    AGENT_VERSION = "v1.0.0"
    AUTHORIZED_TOOLS = ["intent_normalizer", "plan_evaluator", "budget_calculator"]
    
    # Maps intent type to default agent graph
    INTENT_TO_AGENT_MAP = {
        IntentType.DESIGN: [
            "knowledge_retrieval",    # First: find relevant reference circuits
            "circuit_design",         # Then: generate the circuit
            "failure_analysis",       # Then: analyze what could go wrong
            "thermal_analysis",       # Parallel with failure: thermal check
            "schema_validation",      # Validate all outputs
            "engineering_rule",       # Check domain rules
            "confidence_aggregator"   # Final score
        ],
        IntentType.ANALYZE: [
            "knowledge_retrieval",
            "failure_analysis",
            "thermal_analysis",       # Parallel
            "emi_analysis",           # Parallel
            "engineering_rule",
            "safety_auditor",
            "confidence_aggregator"
        ],
        IntentType.TROUBLESHOOT: [
            "knowledge_retrieval",
            "repair_diagnosis",
            "simulation",             # Optional — if netlist available
            "engineering_rule",
            "confidence_aggregator"
        ],
        # ... other intent types
    }
    
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        # Step 1: Normalize the raw intent
        intent = await IntentNormalizer().normalize(task.input_schema["raw_input"], context)
        
        # Step 2: Handle ambiguity before planning
        if intent.requires_clarification and intent.confidence_in_intent < 0.65:
            return self._request_clarification(intent)
        
        # Step 3: Select base agent graph from intent type
        base_agents = self.INTENT_TO_AGENT_MAP.get(intent.primary_intent, [])
        
        # Step 4: Enrich graph based on specific context
        enriched_agents = self._enrich_agent_selection(intent, context, base_agents)
        
        # Step 5: Build dependency graph and parallelization strategy
        execution_order = self._compute_execution_waves(enriched_agents)
        
        # Step 6: Budget each task
        tasks = await self._build_and_budget_tasks(enriched_agents, intent, context)
        
        # Step 7: Choose async vs sync based on estimated duration
        total_tokens = sum(t.token_budget for t in tasks)
        estimated_seconds = self._estimate_duration(tasks)
        
        plan = ExecutionPlan(
            plan_id=generate_id(),
            intent=intent,
            tasks=tasks,
            execution_order=execution_order,
            estimated_total_tokens=total_tokens,
            estimated_duration_seconds=estimated_seconds,
            estimated_cost_usd=self._estimate_cost(tasks),
            requires_async=estimated_seconds > 8,   # > 8 seconds → Celery job
            plan_rationale=self._explain_plan(intent, tasks),
            fallback_plan=self._build_fallback_plan(intent, context)
        )
        
        return AgentResult(
            agent_id=self.AGENT_ID,
            output={"execution_plan": asdict(plan)},
            computed_confidence=0.99,  # Planner always returns a plan; confidence is in the plan's quality
            # ... other fields
        )
    
    def _enrich_agent_selection(
        self, intent: IntentPacket, context: AgentContext, base_agents: list[str]
    ) -> list[str]:
        """Add or remove agents based on specific context signals."""
        agents = list(base_agents)
        
        # If image was uploaded → add vision-capable path
        if context.session_memory.has_uploaded_image:
            agents.insert(0, "vision_preprocessor")
        
        # If user is a student → add learning agent for explanation
        if intent.inferred_skill_level == "student":
            agents.append("learning")
        
        # If high-voltage circuit (> 50V) → mandatory safety audit
        voltages = [float(v.replace("V","")) for v in intent.operating_conditions.get("voltages", []) if v]
        if any(v > 50 for v in voltages):
            if "safety_auditor" not in agents:
                agents.append("safety_auditor")
        
        # If enterprise user → add detailed audit trail generation
        if context.user_plan == "enterprise":
            agents.append("audit_trail_generator")
        
        # Free plan: remove expensive multi-model verification
        if context.user_plan == "free":
            agents = [a for a in agents if a != "cross_model_verifier"]
        
        return agents
    
    def _compute_execution_waves(self, agents: list[str]) -> list[list[str]]:
        """
        Determine which agents can run in parallel (same wave) vs must wait (next wave).
        Parallelizable: agents with no data dependency on each other.
        Sequential: agents that consume another's output.
        """
        PARALLEL_GROUPS = {
            "analysis_wave": ["thermal_analysis", "emi_analysis", "failure_analysis"],
            "validation_wave": ["schema_validation", "engineering_rule", "safety_auditor"]
        }
        
        waves = []
        remaining = list(agents)
        
        # Wave 0: Always knowledge retrieval first (provides RAG context to all others)
        if "knowledge_retrieval" in remaining:
            waves.append(["knowledge_retrieval"])
            remaining.remove("knowledge_retrieval")
        
        # Build subsequent waves using parallel group definitions
        # ... (graph topological sort with parallelism)
        return waves
```

### 3.3 Plan Adaptation at Runtime

The planner does not just create a plan at the start and disappear. It monitors execution and adapts:

```python
class PlanAdaptationEngine:
    """
    Monitors plan execution in real-time and modifies remaining tasks
    based on what has been learned from completed tasks.
    """
    
    async def adapt_plan(
        self, 
        plan: ExecutionPlan, 
        completed_results: list[AgentResult],
        remaining_tasks: list[AgentTask]
    ) -> list[AgentTask]:
        
        adaptation_signals = self._extract_signals(completed_results)
        adapted_tasks = list(remaining_tasks)
        
        # Signal: thermal analysis found critical overheating
        # Adaptation: add cooling recommendation agent to remaining tasks
        if adaptation_signals.get("critical_thermal_violation"):
            adapted_tasks.append(
                AgentTask(agent_type="cooling_advisor", priority=1, is_critical=False, ...)
            )
        
        # Signal: failure analysis found high EMI risk
        # Adaptation: escalate EMI agent to use more powerful model
        if adaptation_signals.get("emi_risk_score") > 7.0:
            for task in adapted_tasks:
                if task.agent_type == "emi_analysis":
                    task.model_requirement = ModelRequirement.POWERFUL
        
        # Signal: multiple validation failures → user input may be ambiguous
        # Adaptation: add clarification request before continuing
        failure_count = sum(1 for r in completed_results if r.status == AgentStatus.FAILED)
        if failure_count > 2:
            adapted_tasks.insert(0, AgentTask(
                agent_type="clarification_requester",
                task_description="Request additional circuit details from user",
                is_critical=True,
                ...
            ))
        
        return adapted_tasks
```

---

## SECTION 4 — SPECIALIZED DOMAIN AGENTS

### 4.1 Failure Analysis Agent

The most complexity-sensitive agent in the system. Combines deterministic rule checking with probabilistic LLM reasoning:

```python
class FailureAnalysisAgent(CognitiveAgent):
    AGENT_ID = "failure_analysis_agent"
    AUTHORIZED_TOOLS = [
        "engineering_rule_engine",    # Deterministic checks
        "llm_reasoner",               # Probabilistic analysis
        "rag_retriever",              # Similar failure case lookup
        "schema_validator"
    ]
    
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        circuit = task.input_schema["circuit_description"]
        reasoning_steps = []
        
        # STAGE 1: Deterministic rule engine (fast, free, always first)
        rule_results = await self._run_rule_engine(circuit)
        reasoning_steps.append(f"Rule engine: {len(rule_results.violations)} violations found")
        
        # STAGE 2: Historical failure retrieval (RAG — grounding the LLM)
        similar_failures = await self._retrieve_similar_failures(circuit, context.rag_context)
        reasoning_steps.append(f"RAG: {len(similar_failures)} similar historical failures retrieved")
        
        # STAGE 3: LLM failure analysis (grounded by stages 1 and 2)
        llm_prompt = FailureAnalysisPrompt().render(
            circuit=circuit,
            rule_violations=rule_results.violations,   # Tell LLM what rules already caught
            historical_failures=similar_failures,       # Ground with real historical data
            operating_conditions=task.input_schema.get("operating_conditions", {}),
            rag_context=context.rag_context
        )
        
        llm_result = await self.llm_reasoner.complete(
            system=llm_prompt,
            temperature=0.1,         # Near-deterministic for safety analysis
            model=task.model_requirement
        )
        reasoning_steps.append("LLM failure analysis completed")
        
        # STAGE 4: Parse and validate LLM output
        parsed = self._parse_and_validate(llm_result, FailurePredictionSchema)
        reasoning_steps.append(f"Schema validation: {'passed' if parsed.valid else 'failed'}")
        
        # STAGE 5: Merge deterministic + probabilistic findings (deduplicate)
        merged_failures = self._merge_findings(rule_results.violations, parsed.output.risks)
        
        # STAGE 6: Compute this agent's confidence
        confidence = self._compute_confidence(
            schema_valid=parsed.valid,
            rule_agreement_rate=self._compute_rule_llm_agreement(rule_results, parsed.output),
            historical_match_quality=similar_failures[0].similarity_score if similar_failures else 0.5,
            llm_self_confidence=parsed.output.get("confidence", 0.7)
        )
        
        return AgentResult(
            agent_id=self.AGENT_ID,
            status=AgentStatus.COMPLETED,
            output={
                "failures": merged_failures,
                "rule_violations": rule_results.violations,
                "llm_additional_risks": parsed.output.risks,
                "severity_distribution": self._compute_severity_distribution(merged_failures)
            },
            reasoning_steps=reasoning_steps,
            computed_confidence=confidence,
            rules_passed=rule_results.passed,
            rules_failed=[v.rule_id for v in rule_results.violations]
        )
    
    def _compute_confidence(
        self, 
        schema_valid: bool,
        rule_agreement_rate: float,
        historical_match_quality: float,
        llm_self_confidence: float
    ) -> float:
        """
        Confidence is a weighted combination of independent signals.
        Each signal is orthogonal — a bad schema doesn't drag down a high historical match.
        """
        if not schema_valid:
            return 0.3   # Schema failure is always low confidence
        
        return (
            0.30 * (1.0 if schema_valid else 0.0) +   # Schema validity: binary gate
            0.35 * rule_agreement_rate +               # Rule-LLM agreement: are they consistent?
            0.20 * historical_match_quality +           # Historical grounding quality
            0.15 * llm_self_confidence                 # LLM's own estimate (least trusted)
        )
```

### 4.2 Simulation Agent

The only agent that interfaces with a deterministic simulation engine (PySpice). Hybrid: simulation for numbers, LLM for interpretation:

```python
class SimulationAgent(CognitiveAgent):
    AGENT_ID = "simulation_agent"
    AUTHORIZED_TOOLS = ["pyspice_runner", "spice_parser", "llm_reasoner", "graph_renderer"]
    
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        netlist = task.input_schema["netlist"]
        simulation_type = task.input_schema.get("simulation_type", "transient")
        
        # STAGE 1: Parse and validate SPICE netlist (before simulation)
        parse_result = await self._parse_netlist(netlist)
        if not parse_result.valid:
            return self._create_parse_failure_result(parse_result.errors)
        
        # STAGE 2: Run deterministic simulation (physics engine, not AI)
        # This runs in executor — PySpice is synchronous and CPU-bound
        loop = asyncio.get_event_loop()
        sim_result = await loop.run_in_executor(
            self.simulation_executor,
            self._run_pyspice_simulation,
            parse_result.circuit,
            simulation_type
        )
        
        if sim_result.failed:
            # Simulation engine failed → LLM attempts to explain what went wrong
            return await self._generate_simulation_failure_explanation(sim_result, context)
        
        # STAGE 3: LLM interprets raw numerical results
        # LLM never sees the netlist raw — it sees structured simulation data
        narrative_prompt = SimulationNarrativePrompt().render(
            simulation_type=simulation_type,
            voltage_nodes=sim_result.voltage_data,
            current_branches=sim_result.current_data,
            frequency_response=sim_result.frequency_data,
            component_list=parse_result.components,
            rag_context=context.rag_context
        )
        
        narrative = await self.llm_reasoner.complete(system=narrative_prompt, temperature=0.3)
        
        # STAGE 4: Extract specific engineering conclusions from narrative
        conclusions = await self._extract_engineering_conclusions(narrative, sim_result)
        
        # Confidence is high when simulation runs successfully (deterministic)
        # LLM narrative confidence is secondary — simulation data is ground truth
        confidence = 0.95 if sim_result.converged else 0.70
        
        return AgentResult(
            agent_id=self.AGENT_ID,
            output={
                "simulation_data": sim_result.to_dict(),
                "narrative": narrative,
                "conclusions": conclusions,
                "simulation_converged": sim_result.converged,
                "data_source": "pyspice_deterministic"  # Always label the data source
            },
            computed_confidence=confidence,
            # ...
        )
```

### 4.3 Knowledge Retrieval Agent

Always the first agent to run in any execution plan. Provides RAG context to all subsequent agents:

```python
class KnowledgeRetrievalAgent(CognitiveAgent):
    AGENT_ID = "knowledge_retrieval_agent"
    AUTHORIZED_TOOLS = ["chromadb_query", "neo4j_query", "result_ranker", "context_assembler"]
    
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        intent = task.input_schema["intent"]
        
        # Run retrieval in parallel — vector search and graph query simultaneously
        vector_results, graph_results = await asyncio.gather(
            self._vector_search(intent, context),
            self._graph_query(intent, context)
        )
        
        # Deduplicate and rank combined results
        merged = self._merge_and_rank(vector_results, graph_results)
        
        # Apply user-specific personalization: boost results from user's own history
        personalized = self._apply_personalization_boost(merged, context.user_id)
        
        # Assemble context block within token budget
        rag_context = self._assemble_context_block(
            results=personalized,
            max_tokens=task.token_budget,
            include_user_history=context.long_term_memory.has_relevant_history(intent)
        )
        
        return AgentResult(
            agent_id=self.AGENT_ID,
            output={
                "rag_context": rag_context,
                "sources_used": [r.source_id for r in personalized[:5]],
                "retrieval_quality": self._assess_retrieval_quality(personalized),
                "user_history_included": context.long_term_memory.has_relevant_history(intent)
            },
            computed_confidence=self._score_retrieval_confidence(personalized),
        )
    
    def _apply_personalization_boost(
        self, results: list[RetrievalResult], user_id: str
    ) -> list[RetrievalResult]:
        """
        Boost relevance scores for results from the user's own engineering history.
        A buck converter circuit the user designed themselves is more relevant than
        a generic reference design — they know the constraints they designed to.
        """
        for result in results:
            if result.metadata.get("user_id") == user_id:
                result.relevance_score = min(1.0, result.relevance_score * 1.35)
            if result.metadata.get("domain") == "user_projects":
                result.relevance_score = min(1.0, result.relevance_score * 1.20)
        
        return sorted(results, key=lambda r: r.relevance_score, reverse=True)
```

---

## SECTION 5 — TOOL EXECUTION GRAPH

### 5.1 Tool Registry

Tools are atomic, single-purpose functions that agents call to interact with external systems. Unlike agents (which reason), tools execute:

```python
# services/cognitive/tool_registry.py

TOOL_REGISTRY: dict[str, "CognitiveTool"] = {}

@dataclass
class ToolCallRecord:
    tool_name: str
    input_summary: str      # Summarized (not full) input for tracing
    output_summary: str     # Summarized output
    duration_ms: int
    success: bool
    error: Optional[str]

class CognitiveTool(ABC):
    TOOL_NAME: str
    DESCRIPTION: str        # Used by Planner to decide which tools to authorize
    COST_ESTIMATE: str      # "free" | "cheap" | "moderate" | "expensive"
    IS_DETERMINISTIC: bool  # True: same input always gives same output
    
    @abstractmethod
    async def invoke(self, **kwargs) -> ToolResult:
        pass

# Tool: Engineering Rule Engine
class EngineeringRuleEngineTool(CognitiveTool):
    TOOL_NAME = "engineering_rule_engine"
    IS_DETERMINISTIC = True
    COST_ESTIMATE = "free"   # Pure Python computation, no API call
    
    RULES = [
        VoltageMarginRule(min_derating=0.80),      # Component must be rated at least 125% of operating voltage
        CurrentRatingRule(max_utilization=0.80),   # Current must not exceed 80% of component rating
        DecouplingRequirementRule(),                # Every IC power pin needs decoupling within 10mm
        FloatingPinRule(),                          # No unconnected digital input pins
        PCBThermalViaRule(min_vias_per_watt=3),    # Power dissipation > 0.5W needs thermal vias
        ESDProtectionRule(required_for_external=True),  # External-facing ports need ESD protection
        BatteryCellBalancingRule(),                 # Multi-cell battery packs need balancing
        GroundPlaneRequirementRule(threshold_freq="10MHz")  # Above 10MHz requires solid ground plane
    ]
    
    async def invoke(self, circuit_description: dict, operating_conditions: dict) -> ToolResult:
        violations = []
        passed = []
        
        for rule in self.RULES:
            if rule.is_applicable(circuit_description):
                result = rule.evaluate(circuit_description, operating_conditions)
                if result.passed:
                    passed.append(result.rule_name)
                else:
                    violations.append(RuleViolation(
                        rule_id=result.rule_id,
                        severity=result.severity,
                        description=result.description,
                        affected_component=result.component,
                        recommended_fix=result.fix
                    ))
        
        return ToolResult(success=True, data={
            "violations": violations,
            "passed_rules": passed,
            "total_rules_checked": len([r for r in self.RULES if r.is_applicable(circuit_description)])
        })

# Tool: PySpice Simulation Runner
class PySpiceSimulationTool(CognitiveTool):
    TOOL_NAME = "pyspice_runner"
    IS_DETERMINISTIC = True
    COST_ESTIMATE = "moderate"   # CPU-bound but no API cost
    
    async def invoke(self, netlist: str, sim_type: str, duration: float) -> ToolResult:
        # Runs in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.cpu_executor,
            self._run_simulation,
            netlist, sim_type, duration
        )
        return ToolResult(success=result.converged, data=result.to_dict())

# Tool: LLM Reasoner (the core AI tool — all agents use this)
class LLMReasonerTool(CognitiveTool):
    TOOL_NAME = "llm_reasoner"
    IS_DETERMINISTIC = False
    COST_ESTIMATE = "expensive"
    
    async def invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        model_requirement: ModelRequirement,
        temperature: float,
        max_tokens: int,
        user_plan: str
    ) -> ToolResult:
        # Route to appropriate provider based on model_requirement and user_plan
        provider = await ProviderRouter().select(model_requirement, user_plan)
        
        response = await provider.complete(
            system=system_prompt,
            user=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return ToolResult(success=True, data={"response": response, "provider": provider.name})
```

### 5.2 Tool Execution Graph — Example: Full Risk Score Analysis

This is the complete tool execution trace for a `POST /analysis/risk-score` request from a Pro plan user:

```
USER SUBMITS: "12V to 3.3V LDO regulator using AMS1117. 500mA load. Running at 45°C ambient."

WAVE 0 — Intent Normalization [1 tool, ~200ms]
└── IntentNormalizerTool
    Input:  raw text
    Output: IntentPacket { primary_intent: ANALYZE, components: ["AMS1117"], voltages: ["12V","3.3V"] }

WAVE 1 — Knowledge Retrieval [2 parallel tools, ~400ms]  
├── ChromaDB Query Tool
│   Input:  "LDO regulator AMS1117 12V 3.3V"
│   Output: 5 similar circuits, 3 similar failure cases, 2 thermal failure cases
└── Neo4j Query Tool  
    Input:  components=["AMS1117"], failure_category="thermal"
    Output: 4 historical AMS1117 failures, 3 confirmed fixes

WAVE 2 — Parallel Domain Analysis [3 parallel agents, ~2000ms]
├── FailureAnalysisAgent
│   ├── EngineeringRuleEngineTool → 2 violations: "AMS1117 Pd at 12V→3.3V/500mA = 4.35W (exceeds SOT-223 limit)"
│   └── LLMReasonerTool (claude-sonnet) → 3 additional LLM-identified risks
│
├── ThermalAnalysisAgent
│   ├── (NumPy) Tj = 45 + (4.35 × 125) = 588.75°C → CRITICAL (max Tj = 125°C)
│   └── LLMReasonerTool → Narrative: "AMS1117 will fail within seconds at this power dissipation"
│
└── EMIAnalysisAgent
    ├── EngineeringRuleEngineTool → 0 violations (LDO is not a switching regulator)
    └── LLMReasonerTool → Output: low EMI risk, 1 decoupling recommendation

WAVE 3 — Validation [2 parallel tools, ~200ms]
├── SchemaValidationAgent → All 3 domain outputs pass schema check
└── SafetyAuditorAgent → CRITICAL: Thermal failure mode constitutes safety hazard

WAVE 4 — Aggregation [1 tool, ~100ms]
└── RiskScoreAggregatorTool
    Inputs:  failure_score=82, thermal_score=98, emi_score=8
    Formula: (0.30 × 82) + (0.30 × 98) + (0.20 × 8) + (0.20 × component_score)
    Output:  final_score=78, severity="CRITICAL", primary_driver="THERMAL"

WAVE 5 — Reflection [1 agent, ~600ms]
└── ReflectionAgent
    Check 1: "Is the thermal violation calculation correct? 12V-3.3V=8.7V drop × 0.5A = 4.35W. Tj=45+(4.35×125)=588°C. YES."
    Check 2: "Does the risk score match the severity of findings? Score=78, thermal=CRITICAL. YES."
    Check 3: "Are recommendations actionable and specific? Buck converter suggestion specific. YES."
    Reflection Result: APPROVED, no correction needed

WAVE 6 — Memory Update [async, non-blocking]
└── MemoryUpdateTask (Celery)
    - Add AMS1117 thermal failure to engineering memory for this user
    - Update user's circuit topology knowledge: "has worked with LDO regulators"
    - Log interaction for prompt regression monitoring

TOTAL: ~3.5 seconds | ~4200 tokens | ~$0.012 | Confidence: 0.94
```

---

## SECTION 6 — MEMORY ARCHITECTURE

QUEBET AI operates with four distinct memory systems. Each has different scope, duration, and engineering purpose:

### 6.1 Memory Type Definitions

```python
# services/cognitive/memory/

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY TYPE 1: Working Memory (Session-Scoped, In-Process)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WorkingMemory:
    """
    Holds the cognitive state of the CURRENT REQUEST ONLY.
    Exists in-process (Python dict, Redis for async jobs).
    Destroyed when the request completes.
    
    Purpose: Share intermediate agent results within a single execution plan.
    The ThermalAnalysisAgent reads the FailureAnalysisAgent's output here
    to avoid re-computing already-extracted facts.
    """
    request_id: str
    execution_plan: ExecutionPlan
    completed_agent_results: dict[str, AgentResult]  # agent_type → result
    accumulated_context: str          # Growing prompt context built across agents
    extracted_facts: dict             # Structured facts extracted from prior agents
    current_circuit_state: dict       # Most current understanding of the circuit
    open_questions: list[str]         # Questions that emerged during analysis

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY TYPE 2: Session Memory (Session-Scoped, Redis-Persisted)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SessionMemory:
    """
    Holds context across MULTIPLE REQUESTS within a single session (browser tab open).
    Persisted in Redis with a 4-hour TTL.
    
    Purpose: "Continue this circuit from before" — the system remembers what
    was discussed earlier in the same working session without requiring the user
    to re-explain the context.
    """
    session_id: str
    user_id: str
    started_at: datetime
    
    # Conversation history (last 20 turns, sliding window)
    conversation_turns: list[ConversationTurn]
    
    # Engineering state for this session
    active_project_id: Optional[str]
    current_circuit: Optional[dict]       # The circuit being worked on
    current_schematic_version: int        # Iteration number of the current design
    
    # Analysis results from this session (avoid re-running)
    cached_analysis: dict[str, AnalysisResult]
    
    # User signals from this session
    user_corrections: list[str]           # "No, I meant 5V not 12V" — tracks corrections
    topics_covered: list[str]             # What concepts came up this session
    has_uploaded_image: bool
    uploaded_image_url: Optional[str]
    
    def add_turn(self, role: str, content: str, metadata: dict = None):
        self.conversation_turns.append(ConversationTurn(role, content, metadata))
        if len(self.conversation_turns) > 20:
            self.conversation_turns.pop(0)  # Sliding window

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY TYPE 3: Long-Term Engineering Memory (User-Scoped, PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LongTermEngineeringMemory:
    """
    Persists ACROSS ALL SESSIONS for a user. Survives browser closes.
    Stored in PostgreSQL `user_engineering_memories` table.
    
    Purpose: The system learns who this engineer is over time — their
    preferred boards, common mistakes, favorite topologies. It becomes
    a personalized engineering copilot, not a generic chatbot.
    """
    user_id: str
    
    # Engineering identity (built from project history)
    preferred_target_boards: list[str]          # ["ESP32", "Arduino Nano"]
    frequently_used_components: list[str]       # ["IRF540N", "LM358", "AMS1117"]
    preferred_circuit_topologies: list[str]     # ["buck converter", "H-bridge"]
    typical_operating_voltages: list[float]     # [3.3, 5.0, 12.0]
    
    # Skill profile (inferred from interactions)
    confirmed_competencies: list[str]           # Topics where user shows mastery
    known_knowledge_gaps: list[str]             # Topics where user repeatedly makes errors
    learning_progression: dict[str, float]      # topic → proficiency (0.0–1.0)
    
    # Design patterns (learn from their history)
    common_design_mistakes: list[DesignPattern] # Mistakes made in past projects
    successful_designs: list[str]               # Circuit types they've successfully built
    
    # Work context
    primary_use_case: str                       # "student_projects" | "product_dev" | "repair"
    location_context: str                       # "india" — for component sourcing relevance
    
    # Preference signals
    preferred_explanation_depth: str            # "brief" | "detailed" | "highly_technical"
    preferred_code_style: str                   # "arduino" | "platformio" | "bare_register"
    
    def get_summary(self) -> str:
        """Returns a compact prompt-injectable summary of this user's engineering profile."""
        return f"""User engineering profile:
Preferred boards: {', '.join(self.preferred_target_boards[:3])}
Common components: {', '.join(self.frequently_used_components[:5])}
Typical voltages: {', '.join(str(v)+'V' for v in self.typical_operating_voltages[:4])}
Skill level: {self._infer_skill_level()}
Known gaps: {', '.join(self.known_knowledge_gaps[:3])}"""

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY TYPE 4: Organizational / Team Memory (Org-Scoped, PostgreSQL + Neo4j)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OrganizationalMemory:
    """
    Enterprise-only. Persists at the ORGANIZATION level, shared across all users.
    Stored in PostgreSQL + Neo4j organization subgraph.
    
    Purpose: Institutional knowledge that should survive individual engineers
    leaving the company. Approved circuits, forbidden components, company
    design standards, historical repair cases from their specific products.
    """
    org_id: str
    org_name: str
    
    # Approved design library
    approved_circuits: list[str]                # Circuit IDs approved by senior engineering review
    approved_component_list: list[str]          # Company-approved vendor components
    forbidden_components: list[str]             # Components banned (EOL, reliability issue, etc.)
    
    # Company standards
    internal_design_rules: list[DesignRule]     # Company-specific DRC rules beyond generic ones
    approved_suppliers: list[str]               # Procurement-approved vendors only
    pcb_fab_constraints: dict                   # Min trace width, drill sizes for their fab
    
    # Historical intelligence
    product_failure_history: list[FailureCase]  # Failures from company's own products
    repair_knowledge_base: list[RepairCase]     # Repair procedures for company's products
    
    # Compliance overlays
    applicable_standards: list[str]             # ["IEC 62368-1", "RoHS", "MIL-STD-461G"]
    certification_requirements: dict            # Per-product certification rules
```

### 6.2 Memory Retrieval — Context Assembly

When an agent executes, it receives a pre-assembled context that pulls from all four memory types:

```python
# services/cognitive/memory/context_assembler.py

class MemoryContextAssembler:
    
    async def assemble_for_agent(
        self, 
        agent_type: str,
        intent: IntentPacket,
        working_memory: WorkingMemory,
        session_memory: SessionMemory,
        long_term_memory: LongTermEngineeringMemory,
        org_memory: Optional[OrganizationalMemory],
        token_budget: int
    ) -> str:
        
        sections = []
        remaining_budget = token_budget
        
        # 1. Working memory (highest priority — most relevant to current task)
        if working_memory.completed_agent_results:
            prior_findings = self._format_prior_findings(working_memory, agent_type)
            sections.append(("prior_findings", prior_findings, 0.30))
        
        # 2. Session memory (current project context)
        if session_memory.current_circuit:
            session_ctx = self._format_session_context(session_memory)
            sections.append(("session_context", session_ctx, 0.25))
        
        # 3. Long-term memory (user identity and patterns)
        user_profile = long_term_memory.get_summary()
        sections.append(("user_profile", user_profile, 0.15))
        
        # 4. Organizational memory (enterprise standards)
        if org_memory and self._is_relevant(org_memory, intent):
            org_ctx = self._format_org_context(org_memory, intent)
            sections.append(("org_standards", org_ctx, 0.20))
        
        # 5. User corrections from session (highest trust — user explicitly said this)
        if session_memory.user_corrections:
            corrections = self._format_corrections(session_memory.user_corrections)
            sections.append(("explicit_user_corrections", corrections, 0.10))
        
        # Fit into token budget using priority weights
        return self._fit_to_budget(sections, token_budget)
    
    def _format_prior_findings(
        self, working_memory: WorkingMemory, current_agent: str
    ) -> str:
        """
        Extract relevant findings from agents that already ran.
        Thermal agent only needs to know failure analysis found overheating risks.
        It doesn't need the EMI findings.
        """
        relevance_map = {
            "thermal_analysis": ["failure_analysis"],    # Thermal cares about failure findings
            "emi_analysis": ["failure_analysis"],         # EMI cares about failure findings
            "confidence_aggregator": ["*"],               # Aggregator sees everything
            "reflection": ["*"]                           # Reflection sees everything
        }
        
        relevant_agents = relevance_map.get(current_agent, [])
        findings = []
        
        for agent_type, result in working_memory.completed_agent_results.items():
            if "*" in relevant_agents or agent_type in relevant_agents:
                findings.append(f"[{agent_type} findings]: {json.dumps(result.output, indent=2)}")
        
        return "\n".join(findings) if findings else ""
```

---

## SECTION 7 — SELF-REFLECTION LOOP

The reflection system is what makes QUEBET AI's outputs trustworthy. Before any analysis result reaches a user, it passes through a reflection cycle that challenges the reasoning that produced it.

### 7.1 Reflection Agent Architecture

```python
# services/cognitive/reflection_agent.py

class ReflectionAgent(CognitiveAgent):
    """
    The intellectual adversary of every other agent.
    
    The Reflection Agent receives all completed domain agent outputs and
    attempts to find:
    1. Internal contradictions between agents
    2. Conclusions that don't follow from the evidence
    3. Missing analysis that should have been performed
    4. Recommendations that are physically impossible
    5. Confidence scores that are inconsistent with finding severity
    
    It operates on the principle of "red team thinking" — it is trying
    to find problems, not confirm correctness.
    """
    
    AGENT_ID = "reflection_agent"
    REFLECTION_DEPTH: ReflectionDepth  # SHALLOW | STANDARD | DEEP
    
    REFLECTION_CHECKS = [
        InternalConsistencyCheck(),    # Do agents agree with each other?
        PhysicsConstraintCheck(),      # Are recommendations physically possible?
        LogicalCohesionCheck(),        # Do conclusions follow from evidence?
        CompletenessCheck(),           # Did we miss any important analysis?
        ConfidenceCalibrationCheck(),  # Is confidence appropriate for findings?
        SafetyComplianceCheck(),       # Do any outputs violate safety rules?
        ActionabilityCheck()           # Are recommendations specific enough to act on?
    ]
    
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        all_results = task.input_schema["agent_results"]  # All domain agent outputs
        corrections = []
        passed_checks = []
        
        for check in self.REFLECTION_CHECKS:
            check_result = await check.evaluate(all_results, context)
            
            if check_result.passed:
                passed_checks.append(check.name)
            else:
                corrections.append(ReflectionCorrection(
                    check_name=check.name,
                    problem_description=check_result.problem,
                    affected_agents=check_result.affected_agents,
                    correction_type=check_result.correction_type,
                    correction_instruction=check_result.correction
                ))
        
        # Classify the severity of corrections found
        if not corrections:
            return self._approve(all_results, passed_checks)
        
        critical_corrections = [c for c in corrections if c.is_critical]
        
        if critical_corrections:
            # Critical issues: trigger re-execution of affected agents
            return self._request_reexecution(critical_corrections, all_results)
        else:
            # Non-critical issues: apply inline corrections and approve with caveat
            corrected_results = await self._apply_corrections(corrections, all_results)
            return self._approve_with_corrections(corrected_results, corrections)
    
    async def _apply_corrections(
        self, corrections: list[ReflectionCorrection], results: dict
    ) -> dict:
        """
        Apply non-critical corrections directly without re-running agents.
        Example: adjust a confidence score that is too high given finding severity.
        """
        corrected = dict(results)
        
        for correction in corrections:
            if correction.correction_type == CorrectionType.ADJUST_CONFIDENCE:
                # Lower confidence of overconfident agent
                for agent_id in correction.affected_agents:
                    if agent_id in corrected:
                        old_conf = corrected[agent_id].computed_confidence
                        corrected[agent_id].computed_confidence = correction.corrected_confidence
                        corrected[agent_id].reasoning_steps.append(
                            f"[REFLECTION CORRECTION] Confidence adjusted from {old_conf:.2f} to "
                            f"{correction.corrected_confidence:.2f}: {correction.problem_description}"
                        )
            
            elif correction.correction_type == CorrectionType.ADD_RECOMMENDATION:
                # Add a recommendation that was clearly missing
                target_result = corrected.get(correction.affected_agents[0])
                if target_result:
                    target_result.output["recommendations"].insert(0, correction.correction_instruction)
        
        return corrected

# ─────────────────────────────────────────────────────────────────────────────
# REFLECTION CHECK: Internal Consistency
# ─────────────────────────────────────────────────────────────────────────────

class InternalConsistencyCheck:
    name = "internal_consistency"
    
    async def evaluate(
        self, all_results: dict[str, AgentResult], context: AgentContext
    ) -> CheckResult:
        """
        Find contradictions between agents.
        
        Example: FailureAnalysisAgent says "no thermal risk" but
        ThermalAnalysisAgent calculated Tj = 200°C (max is 125°C).
        That is a critical contradiction.
        """
        contradictions = []
        
        failure_result = all_results.get("failure_analysis")
        thermal_result = all_results.get("thermal_analysis")
        
        if failure_result and thermal_result:
            # Check: does failure agent's thermal assessment agree with thermal agent?
            failure_says_thermal_ok = not any(
                "thermal" in r.lower() for r in failure_result.output.get("failures", [])
            )
            thermal_says_critical = any(
                c["exceeds_max_tj"] 
                for c in thermal_result.output.get("components", [])
            )
            
            if failure_says_thermal_ok and thermal_says_critical:
                contradictions.append(
                    "FailureAnalysisAgent reports no thermal risk, but ThermalAnalysisAgent "
                    "found components exceeding maximum junction temperature. "
                    "FailureAnalysis result must be updated to include thermal violations."
                )
        
        if contradictions:
            return CheckResult(
                passed=False,
                problem="; ".join(contradictions),
                affected_agents=["failure_analysis"],
                correction_type=CorrectionType.RERUN_AGENT,
                is_critical=True
            )
        
        return CheckResult(passed=True)

# ─────────────────────────────────────────────────────────────────────────────
# REFLECTION CHECK: Physics Constraint
# ─────────────────────────────────────────────────────────────────────────────

class PhysicsConstraintCheck:
    name = "physics_constraints"
    
    PHYSICS_RULES = {
        "thermal": lambda tj: 0 <= tj <= 300,           # Junction temp must be physically possible
        "voltage": lambda v: 0 <= v <= 10000,            # Voltage must be positive and sane
        "current": lambda i: i >= 0,                     # Current cannot be negative in DC context
        "resistance": lambda r: r > 0,                   # Resistance must be positive
        "frequency": lambda f: f > 0,                    # Frequency must be positive
    }
    
    async def evaluate(self, all_results: dict, context: AgentContext) -> CheckResult:
        violations = []
        
        for agent_id, result in all_results.items():
            for quantity, validator in self.PHYSICS_RULES.items():
                values = self._extract_quantities(result.output, quantity)
                for val, location in values:
                    if not validator(val):
                        violations.append(
                            f"{agent_id} produced physically impossible {quantity}={val} at {location}"
                        )
        
        if violations:
            return CheckResult(passed=False, problem="; ".join(violations), is_critical=True)
        return CheckResult(passed=True)
```

### 7.2 Reflection Loop Depth Control

Reflection depth is calibrated to request type, user plan, and stakes:

```python
class ReflectionDepthSelector:
    
    def select_depth(
        self,
        intent: IntentPacket,
        user_plan: str,
        operating_voltage: float,
        involves_mains_power: bool
    ) -> ReflectionDepth:
        
        # Safety-critical: always deep reflection
        if involves_mains_power or operating_voltage > 60:
            return ReflectionDepth.DEEP
        
        # Enterprise plan: thorough reflection (they pay for it)
        if user_plan == "enterprise":
            return ReflectionDepth.DEEP
        
        # Pro plan, analysis task: standard reflection
        if user_plan == "pro" and intent.primary_intent in [IntentType.ANALYZE, IntentType.DESIGN]:
            return ReflectionDepth.STANDARD
        
        # Free plan or learning queries: shallow reflection (cost control)
        return ReflectionDepth.SHALLOW

REFLECTION_DEPTH_SPECS = {
    ReflectionDepth.SHALLOW: {
        "checks_enabled": ["internal_consistency", "physics_constraints"],
        "max_corrections": 2,
        "rerun_on_critical": False,  # Just flag the issue, don't rerun
        "token_budget": 500
    },
    ReflectionDepth.STANDARD: {
        "checks_enabled": ["internal_consistency", "physics_constraints", 
                           "logical_cohesion", "actionability"],
        "max_corrections": 5,
        "rerun_on_critical": True,
        "token_budget": 1000
    },
    ReflectionDepth.DEEP: {
        "checks_enabled": "all",
        "max_corrections": 10,
        "rerun_on_critical": True,
        "max_reruns": 2,           # Can trigger up to 2 re-execution cycles
        "token_budget": 2000
    }
}
```

---

## SECTION 8 — CONFIDENCE AGGREGATION

### 8.1 Confidence Signal Model

Confidence in QUEBET AI is not a single number returned by a model — it is a multi-signal composite computed from independent sources:

```python
# services/cognitive/confidence_aggregator.py

@dataclass
class ConfidenceSignals:
    """All signals that contribute to the final confidence score."""
    
    # Deterministic signals (highest trust — computed, not estimated)
    schema_validation_passed: bool          # Weight: 0.20
    engineering_rules_pass_rate: float      # 0.0–1.0 | Weight: 0.25
    physics_constraints_valid: bool         # Weight: 0.15
    
    # Probabilistic signals (medium trust)
    rag_retrieval_quality: float            # How well RAG context matched | Weight: 0.15
    cross_agent_agreement_rate: float       # Do multiple agents agree? | Weight: 0.10
    historical_match_strength: float        # Similar past cases exist? | Weight: 0.10
    
    # Model-reported signals (lowest trust — model is often overconfident)
    llm_self_confidence: float              # What the model said | Weight: 0.05
    
    # Reflection signals (post-hoc correction)
    reflection_corrections_applied: int     # More corrections → lower confidence
    reflection_checks_passed_rate: float    # Weight: applied as multiplier

class ConfidenceAggregatorAgent(CognitiveAgent):
    
    SIGNAL_WEIGHTS = {
        "schema_validation": 0.20,
        "engineering_rules": 0.25,
        "physics_valid": 0.15,
        "rag_quality": 0.15,
        "cross_agent_agreement": 0.10,
        "historical_match": 0.10,
        "llm_self_report": 0.05,
        # Remaining 0.0: reflection multiplier applied after weighted sum
    }
    
    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        all_results: list[AgentResult] = task.input_schema["all_agent_results"]
        signals = self._extract_signals(all_results)
        
        # Compute weighted base score
        base_confidence = (
            self.SIGNAL_WEIGHTS["schema_validation"] * (1.0 if signals.schema_validation_passed else 0.0) +
            self.SIGNAL_WEIGHTS["engineering_rules"] * signals.engineering_rules_pass_rate +
            self.SIGNAL_WEIGHTS["physics_valid"] * (1.0 if signals.physics_constraints_valid else 0.0) +
            self.SIGNAL_WEIGHTS["rag_quality"] * signals.rag_retrieval_quality +
            self.SIGNAL_WEIGHTS["cross_agent_agreement"] * signals.cross_agent_agreement_rate +
            self.SIGNAL_WEIGHTS["historical_match"] * signals.historical_match_strength +
            self.SIGNAL_WEIGHTS["llm_self_report"] * signals.llm_self_confidence
        )
        
        # Apply reflection multiplier (corrections reduce confidence)
        reflection_multiplier = max(
            0.5,  # Floor: reflection can reduce confidence at most by 50%
            1.0 - (signals.reflection_corrections_applied * 0.08)  # Each correction: -8%
        )
        
        # Hard gates — certain failures always result in specific confidence ceilings
        final_confidence = base_confidence * reflection_multiplier
        
        if not signals.schema_validation_passed:
            final_confidence = min(final_confidence, 0.40)   # Schema fail: hard ceiling at 40%
        
        if not signals.physics_constraints_valid:
            final_confidence = min(final_confidence, 0.30)   # Physics violation: ceiling at 30%
        
        routing = self._determine_routing(final_confidence)
        
        return AgentResult(
            agent_id=self.AGENT_ID,
            output={
                "final_confidence": round(final_confidence, 3),
                "signal_breakdown": asdict(signals),
                "routing_decision": routing,
                "explanation": self._explain_confidence(signals, final_confidence)
            },
            computed_confidence=final_confidence
        )
    
    def _determine_routing(self, confidence: float) -> ConfidenceRouting:
        if confidence >= 0.90:
            return ConfidenceRouting.DELIVER_DIRECTLY
        elif confidence >= 0.75:
            return ConfidenceRouting.DELIVER_WITH_WARNING
        elif confidence >= 0.60:
            return ConfidenceRouting.SOFT_RETRY           # Retry with same model, lower temp
        elif confidence >= 0.40:
            return ConfidenceRouting.ESCALATE_MODEL       # Retry with more powerful model
        else:
            return ConfidenceRouting.REQUEST_MORE_INPUT   # User must provide more detail
```

---

## SECTION 9 — AUTONOMOUS DEBUGGING WORKFLOW

The autonomous debugging workflow is QUEBET's most sophisticated agentic behavior. Unlike single-turn analysis, autonomous debugging runs a multi-turn investigation loop that progressively narrows to a root cause without requiring human input at each step.

### 9.1 Debug Session State Machine

```python
class DebugSessionState(str, Enum):
    SYMPTOM_RECEIVED      = "symptom_received"
    HYPOTHESIS_GENERATED  = "hypothesis_generated"
    TEST_PLAN_CREATED     = "test_plan_created"
    AWAITING_MEASUREMENT  = "awaiting_measurement"   # Only state that waits for user
    MEASUREMENT_RECEIVED  = "measurement_received"
    HYPOTHESIS_NARROWED   = "hypothesis_narrowed"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    FIX_RECOMMENDED       = "fix_recommended"
    VERIFICATION_PENDING  = "verification_pending"   # User applies fix, reports result
    RESOLVED              = "resolved"
    ESCALATED             = "escalated"              # System exhausted its knowledge

class AutonomousDebugOrchestrator:
    """
    Manages a multi-turn hardware debugging investigation.
    
    The system autonomously generates hypotheses, designs tests, interprets
    results, narrows hypotheses, and iterates — only pausing to ask the user
    for actual measurements that require a multimeter or oscilloscope.
    
    The user provides: physical measurements
    The system provides: everything else
    """
    
    MAX_DEBUG_ITERATIONS = 8       # After 8 iterations without resolution → escalate
    MIN_CONFIDENCE_TO_CONCLUDE = 0.82  # Must be this confident before declaring root cause
    
    async def run_debug_session(
        self, 
        symptom: str, 
        circuit_description: Optional[str],
        session_id: str,
        context: AgentContext
    ) -> AsyncGenerator[DebugUpdate, None]:
        
        state = DebugSessionState.SYMPTOM_RECEIVED
        hypotheses: list[Hypothesis] = []
        test_results: list[TestResult] = []
        iteration = 0
        
        while state != DebugSessionState.RESOLVED and iteration < self.MAX_DEBUG_ITERATIONS:
            iteration += 1
            
            # ── STAGE 1: Generate or narrow hypotheses ──────────────────────
            if state == DebugSessionState.SYMPTOM_RECEIVED:
                hypotheses = await self._generate_initial_hypotheses(
                    symptom, circuit_description, context
                )
                state = DebugSessionState.HYPOTHESIS_GENERATED
                yield DebugUpdate(state=state, hypotheses=hypotheses)
            
            elif state == DebugSessionState.MEASUREMENT_RECEIVED:
                hypotheses = await self._narrow_hypotheses(
                    hypotheses, test_results, context
                )
                
                # Check if we've converged on a single high-confidence hypothesis
                top_hypothesis = max(hypotheses, key=lambda h: h.confidence)
                if top_hypothesis.confidence >= self.MIN_CONFIDENCE_TO_CONCLUDE:
                    state = DebugSessionState.ROOT_CAUSE_IDENTIFIED
                    yield DebugUpdate(state=state, root_cause=top_hypothesis)
                    break
                
                state = DebugSessionState.HYPOTHESIS_NARROWED
            
            # ── STAGE 2: Design the optimal test for remaining hypotheses ────
            if state in [DebugSessionState.HYPOTHESIS_GENERATED, 
                         DebugSessionState.HYPOTHESIS_NARROWED]:
                
                test_plan = await self._design_discriminating_test(
                    hypotheses=hypotheses,
                    tests_already_run=test_results,
                    available_instruments=context.session_memory.available_instruments
                )
                
                state = DebugSessionState.AWAITING_MEASUREMENT
                yield DebugUpdate(
                    state=state, 
                    test_instruction=test_plan,
                    # Pause here — waiting for user to take the measurement
                )
                return   # The next call resumes with measurement_result
            
            # ── STAGE 3: Generate fix recommendation ─────────────────────────
            if state == DebugSessionState.ROOT_CAUSE_IDENTIFIED:
                fix = await self._generate_fix(hypotheses[0], circuit_description, context)
                state = DebugSessionState.FIX_RECOMMENDED
                yield DebugUpdate(state=state, fix_recommendation=fix)
                break
        
        if iteration >= self.MAX_DEBUG_ITERATIONS:
            yield DebugUpdate(state=DebugSessionState.ESCALATED)
    
    async def _generate_initial_hypotheses(
        self,
        symptom: str,
        circuit_description: Optional[str],
        context: AgentContext
    ) -> list[Hypothesis]:
        """
        Generates 3–6 ranked hypotheses for what could cause the observed symptom.
        Uses historical failure graph + LLM reasoning.
        """
        # Query Neo4j for historically similar symptoms
        graph_results = await self.graph_queries.find_similar_symptoms(
            symptom=symptom,
            circuit_type=self._infer_circuit_type(circuit_description)
        )
        
        # LLM generates hypotheses grounded in historical data
        prompt = DebugHypothesisPrompt().render(
            symptom=symptom,
            circuit=circuit_description,
            historical_failures=graph_results,
            rag_context=context.rag_context
        )
        
        llm_output = await self.llm_tool.invoke(
            system_prompt=prompt,
            temperature=0.15,
            model_requirement=ModelRequirement.STANDARD
        )
        
        return self._parse_hypotheses(llm_output, graph_results)
    
    async def _design_discriminating_test(
        self,
        hypotheses: list[Hypothesis],
        tests_already_run: list[TestResult],
        available_instruments: list[str]
    ) -> TestInstruction:
        """
        Chooses the single most information-efficient test to run next.
        Uses information-theoretic reasoning: which test eliminates the most
        hypotheses regardless of the result?
        
        This is the same reasoning a skilled debugging engineer uses:
        "If I probe this test point and get 3.3V, that eliminates hypotheses 2 and 4.
        If I get 0V, it eliminates hypotheses 1 and 3. Either way, I've halved my space."
        """
        prompt = DiscriminatingTestDesignPrompt().render(
            active_hypotheses=hypotheses,
            tests_already_run=tests_already_run,
            available_instruments=available_instruments
        )
        
        test_plan = await self.llm_tool.invoke(system_prompt=prompt, temperature=0.05)
        
        return TestInstruction(
            test_point=test_plan["test_point"],
            measurement_type=test_plan["measurement_type"],  # DC voltage, resistance, frequency
            expected_if_healthy=test_plan["expected_healthy"],
            expected_per_hypothesis=test_plan["expected_per_hypothesis"],
            instrument_settings=test_plan["instrument_settings"],
            safety_note=test_plan.get("safety_note"),
            why_this_test=test_plan["rationale"]
        )
```

---

## SECTION 10 — ADAPTIVE ORCHESTRATION

### 10.1 Runtime Model Selection

The orchestration layer continuously optimizes which model executes each task based on real-time signals:

```python
# services/cognitive/adaptive_orchestrator.py

class AdaptiveOrchestrator:
    """
    Makes real-time decisions about model selection, parallelization,
    and resource allocation based on current system state.
    """
    
    async def select_model_for_task(
        self,
        task: AgentTask,
        context: AgentContext,
        system_state: SystemState
    ) -> ModelSelection:
        
        # Base model from task requirement
        base_model = MODEL_CAPABILITY_MAP[task.model_requirement]
        
        # Downgrade if: free plan user, low-complexity task, or system under load
        if context.user_plan == "free":
            return ModelSelection(model="qwen-2.5", reason="free_plan_policy")
        
        if system_state.provider_latency["claude"] > 5000:  # Claude slow right now
            if base_model.startswith("claude"):
                return ModelSelection(model="gpt-4o", reason="provider_latency_fallback")
        
        if task.model_requirement == ModelRequirement.FAST:
            return ModelSelection(model="claude-3-haiku", reason="fast_task_optimized")
        
        # Upgrade if: critical safety check, enterprise plan, high-stakes output
        if task.is_critical and context.user_plan in ["pro", "enterprise"]:
            return ModelSelection(model="claude-3-5-sonnet", reason="critical_task_upgrade")
        
        return ModelSelection(model=base_model, reason="standard_routing")
    
    async def optimize_parallelization(
        self,
        remaining_tasks: list[AgentTask],
        available_worker_slots: int,
        remaining_token_budget: int
    ) -> list[list[AgentTask]]:
        """
        Dynamically re-evaluate which remaining tasks can run in parallel
        given current worker availability and token budget.
        """
        # Group tasks by dependency level (topological sort)
        levels = self._topological_sort(remaining_tasks)
        
        optimized = []
        for level in levels:
            # From tasks available at this level, select those that fit in budget and slots
            token_remaining = remaining_token_budget
            slot_remaining = available_worker_slots
            wave = []
            
            # Sort by priority (highest first) within each dependency level
            sorted_level = sorted(level, key=lambda t: t.priority)
            
            for task in sorted_level:
                task_tokens = task.token_budget
                if token_remaining >= task_tokens and slot_remaining > 0:
                    wave.append(task)
                    token_remaining -= task_tokens
                    slot_remaining -= 1
            
            if wave:
                optimized.append(wave)
        
        return optimized
    
    async def handle_agent_failure(
        self,
        failed_agent: AgentResult,
        execution_plan: ExecutionPlan,
        context: AgentContext
    ) -> FailureResponse:
        """
        Intelligent failure handling — not all failures are equal.
        """
        
        if failed_agent.status == AgentStatus.ESCALATED:
            # Low confidence — escalate to stronger model
            new_task = self._create_escalated_task(
                failed_agent, 
                stronger_model=self._get_next_model_tier(failed_agent.models_consulted[0])
            )
            return FailureResponse(action="ESCALATE", new_task=new_task)
        
        if failed_agent.status == AgentStatus.FAILED:
            # Check if this was a critical path agent
            if self._is_critical_path(failed_agent.agent_id, execution_plan):
                # Critical failure — notify user, cannot produce output
                return FailureResponse(
                    action="ABORT",
                    user_message=f"Analysis could not complete due to {failed_agent.agent_id} failure. "
                                 f"Please try again or provide more circuit detail."
                )
            else:
                # Non-critical failure — continue without this agent's output
                return FailureResponse(
                    action="SKIP",
                    caveat=f"Note: {failed_agent.agent_type} analysis was unavailable. "
                           f"Result excludes this perspective."
                )
```

### 10.2 Continuous Learning Loop

```python
class CognitiveLearningLoop:
    """
    Runs asynchronously after every interaction.
    Updates the system's models, weights, and knowledge based on outcomes.
    Never blocks user-facing response delivery.
    """
    
    @celery.task(queue="low_priority")
    async def post_interaction_learning(
        self,
        interaction_record: InteractionRecord,
        user_feedback: Optional[UserFeedback]
    ):
        tasks = []
        
        # 1. Update long-term engineering memory (always)
        tasks.append(self._update_engineering_memory(interaction_record))
        
        # 2. Update Neo4j knowledge graph if new failure pattern identified
        if interaction_record.contains_new_failure_pattern():
            tasks.append(self._add_failure_to_graph(interaction_record))
        
        # 3. Update embedding weights if user explicitly corrected the system
        if user_feedback and user_feedback.type == FeedbackType.CORRECTION:
            tasks.append(self._record_correction_for_prompt_review(
                interaction_record, user_feedback
            ))
        
        # 4. Update confidence calibration if user confirmed or denied root cause
        if user_feedback and user_feedback.type == FeedbackType.OUTCOME_REPORT:
            tasks.append(self._recalibrate_confidence_weights(
                interaction_record, user_feedback.was_correct
            ))
        
        # 5. Update session memory with new topics and patterns
        tasks.append(self._update_session_memory(interaction_record))
        
        await asyncio.gather(*tasks)
```

---

## SECTION 11 — FULL COGNITIVE EXECUTION TRACE

A complete, annotated trace of cognitive processing for a non-trivial engineering request:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUEBET AI — COGNITIVE EXECUTION TRACE
Request: "My ESP32-WROOM dev board works fine on USB but keeps 
          resetting when powered from a 9V battery through a 
          7805 regulator. What's wrong?"
User: Pro plan | Long-term memory: 4 past ESP32 projects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[T+0ms]    IntentNormalizer
           primary_intent: TROUBLESHOOT
           components: ["ESP32-WROOM", "7805", "9V battery"]
           symptom: "resets under battery power but not USB"
           confidence_in_intent: 0.97

[T+80ms]   CognitivePlannerAgent
           Selected agents: [knowledge_retrieval, repair_diagnosis,
                             thermal_analysis, simulation(optional),
                             engineering_rule, confidence_aggregator]
           Execution waves: [[retrieval], [diagnosis+thermal], [rule], [aggregator]]
           Estimated duration: 4.2s | Estimated cost: $0.008
           Route: SYNC (< 8 seconds estimated)

[T+90ms]   WAVE 1 START: KnowledgeRetrievalAgent
           ChromaDB query: "ESP32 reset battery 7805 regulator"
             Retrieved: 6 similar cases
             Top match (0.94): "ESP32 brownout from inadequate 5V supply capacitance"
             Top match (0.89): "7805 thermal shutdown causing resets"
             Top match (0.87): "9V PP3 battery internal resistance causing voltage sag"
           Neo4j query: Component=ESP32, Failure=brownout_reset
             Found: 12 historical cases | Most common fix: bulk capacitance

[T+430ms]  WAVE 2 START: Parallel execution

           ┌── RepairDiagnosisAgent ──────────────────────────────────────
           │  EngineeringRuleEngine: 
           │    Rule: ESP32 requires ≥100µF at 3.3V rail — CHECK
           │    Rule: 7805 requires ≥0.1µF input, ≥0.33µF output — UNKNOWN
           │    Rule: Battery ESR × peak current < voltage margin — CHECK
           │  
           │  LLM (claude-3-5-sonnet, temp=0.1):
           │    Primary diagnosis: "9V PP3 battery has internal resistance 
           │    ~2-4Ω. ESP32 WiFi draws 500mA peaks. Voltage sag = 1-2V.
           │    7805 input may drop below 7V minimum headroom.
           │    7805 output drops → ESP32 brownout threshold triggered."
           │    Confidence self-report: 0.87
           │  
           │  Result: 3 hypotheses ranked by probability:
           │    H1 (0.82): Insufficient input voltage headroom under load
           │    H2 (0.71): Insufficient output capacitance causing brownout
           │    H3 (0.45): 7805 thermal shutdown from poor heatsinking
           └──────────────────────────────────────────────────────────────
           
           ┌── ThermalAnalysisAgent ─────────────────────────────────────
           │  (NumPy) 7805: Pd = (9V - 5V) × 0.5A = 2W
           │  Tj = 25 + (2W × 65°C/W [7805 TO-220, no heatsink])
           │  Tj = 25 + 130 = 155°C   >  MAX 125°C
           │  → 7805 WILL thermally shutdown under sustained load
           │  
           │  Thermal finding: H3 confirmed as real secondary risk
           │  Confidence: 0.95 (deterministic calculation)
           └──────────────────────────────────────────────────────────────

[T+2100ms] WAVE 3: EngineeringRuleAgent
           Checks all repair diagnosis and thermal outputs:
             PASS: Voltage analysis follows Ohm's law
             PASS: Thermal calculation uses correct Rθja for 7805 TO-220
             FAIL: Recommendations don't mention current limiting
           Added recommendation: current sense circuit for ESP32 supply

[T+2300ms] ReflectionAgent (STANDARD depth — Pro plan)
           Check 1 [InternalConsistency]: 
             RepairDiagnosis says "H3 is 45% likely (thermal shutdown)"
             Thermal says "Tj = 155°C — thermal shutdown WILL occur"
             → CONTRADICTION: repair agent underweighted thermal risk
             → CORRECTION: boost H3 to 0.78, add thermal shutdown as co-cause
           
           Check 2 [PhysicsConstraints]: All values physically valid. PASS.
           Check 3 [Completeness]: Battery ESR calculation not quantified.
             → ADD: "Measure battery voltage under load to verify sag"
           Check 4 [Actionability]: Test points specified. PASS.
           
           Applied 2 corrections. Reflection result: APPROVED WITH CORRECTIONS.

[T+2900ms] ConfidenceAggregatorAgent
           Schema valid:          1.00 × 0.20 = 0.200
           Engineering rules:     0.89 × 0.25 = 0.223
           Physics valid:         1.00 × 0.15 = 0.150
           RAG quality:           0.94 × 0.15 = 0.141
           Cross-agent agreement: 0.78 × 0.10 = 0.078
           Historical match:      0.91 × 0.10 = 0.091
           LLM self-report:       0.87 × 0.05 = 0.044
           ─────────────────────────────────────────
           Base score:                          0.927
           Reflection multiplier: 1.0-(2×0.08)= 0.84
           Final confidence:      0.927 × 0.84 = 0.779
           Routing: DELIVER_WITH_WARNING (≥0.75)

[T+3100ms] ResponseAssembler — Final structured output:
           {
             "root_causes": [
               {"hypothesis": "7805 thermal shutdown under sustained load",
                "confidence": 0.78, "verified_by": ["thermal_analysis", "engineering_rule"]},
               {"hypothesis": "9V battery voltage sag below 7805 minimum headroom",
                "confidence": 0.82, "verified_by": ["repair_diagnosis", "historical_data"]}
             ],
             "diagnostic_tests": [
               {"step": 1, "action": "Measure battery terminal voltage while ESP32 is resetting",
                "expected_healthy": ">7.5V", "if_below": "battery sag confirmed — replace with 12V supply"},
               {"step": 2, "action": "Touch 7805 body after 30 seconds of operation",
                "expected_healthy": "warm but touchable", "if_burning_hot": "thermal shutdown confirmed"}
             ],
             "fixes": [
               {"priority": 1, "action": "Replace 7805 with 12V-input LDO (HT7533) or buck converter",
                "reason": "7805 dissipates 2W with 9V input — exceeds TO-220 junction temperature"},
               {"priority": 2, "action": "Add 1000µF bulk capacitor at 7805 output + 100µF at ESP32 3.3V",
                "reason": "Absorbs WiFi transmit current spikes without voltage drop"}
             ],
             "confidence": 0.779,
             "confidence_note": "High confidence. Consider providing battery voltage measurement for definitive confirmation.",
             "sources": ["12_historical_ESP32_brownout_cases", "7805_thermal_analysis", "engineering_rule_engine"],
             "verification_status": "schema_valid | physics_valid | reflection_approved",
             "prompt_versions": ["repair_diagnosis_v2.1.0", "thermal_v1.3.0"],
             "trace_id": "cog_trace_8f2a3b4c"
           }

[T+3100ms] Response delivered to user
[T+3101ms] Memory update tasks queued (Celery, non-blocking):
           - Log ESP32+7805 thermal case to Neo4j
           - Update user's long-term memory: "thermal issues in 7805 circuits"
           - Increment 7805 thermal failure counter in knowledge graph
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL TIME:  3.1 seconds
AGENTS RUN:  6 (1 orchestrator + 3 domain + 1 reflection + 1 aggregator)
TOKENS USED: 3,847
COST:        $0.0091
CONFIDENCE:  0.779 (high — delivered with advisory)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## SECTION 12 — ARCHITECTURE EVOLUTION ROADMAP

```
PHASE 1 — Foundation (Current)
  ├── Single-agent per request with basic validation
  ├── Prompt-level Redis cache
  ├── Schema validation on all outputs
  └── Basic session memory (Redis)

PHASE 2 — Multi-Agent (Next 6 months)
  ├── CognitivePlannerAgent live
  ├── Parallel domain agent execution (waves)
  ├── ReflectionAgent on Pro/Enterprise
  ├── ConfidenceAggregator with signal model
  ├── Long-term engineering memory (PostgreSQL)
  └── Autonomous debug session (basic)

PHASE 3 — Adaptive Intelligence (6–12 months)
  ├── Plan adaptation at runtime
  ├── Full organizational memory (Enterprise)
  ├── Deep reflection with agent re-execution
  ├── Continuous learning loop (post-interaction)
  ├── Cross-session personalization
  └── Autonomous debug with instrument guidance

PHASE 4 — Cognitive OS (12–18 months)
  ├── Self-improving knowledge graph
  ├── Autonomous design review (no user prompt)
  ├── Multi-user collaborative agent sessions
  ├── Manufacturing feedback integration
  ├── Confidence calibration self-tuning
  └── Domain-specific fine-tuned models on QUEBET corpus
```

---

*Document Owner: AI Systems Architecture Team*
*Review Cycle: Monthly during active development*
*Dependencies: 03_ai_orchestration.md, 09_database_and_rag_design.md, 07_quality_control_and_verification.md*
*Implementation Priority: Phase 2 begins after core platform MVP (Phase 1) reaches 1,000 active users*
