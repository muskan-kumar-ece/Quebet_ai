"use client";

import React, { useState, useEffect } from "react";
import {
  Brain,
  Sparkles,
  Play,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Shield,
  Layers,
  FileText,
  Search,
  ArrowRight,
  GitBranch,
  RefreshCw,
  Cpu,
  Zap,
  Info,
  Lock,
  Compass,
  ListOrdered,
  Activity,
  ChevronRight,
  CheckSquare,
  Scale,
  SearchX,
  Repeat,
  FileSearch,
  Gavel,
  Check,
  AlertOctagon,
  FileCheck,
  ShieldAlert,
  History,
  BookOpen,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  BookmarkCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import {
  EngineeringIntentPacket,
  EngineeringTaskPlan,
  PlanValidationResult,
  CognitiveExecution,
  CognitiveExplanation,
  IntentAmbiguity,
  ContextSnapshot,
  EngineeringReflection,
  EngineeringReasoningFinding,
  ReflectionReplanResult,
  EngineeringDecisionBrief,
  DecisionBriefStatus,
  HumanDecisionType,
  DecisionAlternative,
  DecisionQuestion,
  MemoryType,
  HistoricalOutcome,
  MemoryApplicability,
  MemoryFeedbackType,
  EngineeringMemoryRecord,
  EngineeringMemoryFeedback,
  SurfacedMemoryItem,
  MemoryRetrievalResponse,
  EngineeringContextSnapshot,
  ContextSnapshotStatus,
  EngineeringContextConflict,
  ContextExplanationResponse,
  EngineeringCognitiveWorkflow,
  CognitiveWorkflowStatus,
  WorkflowTimelineStep,
  ExplanationCategory,
  EngineeringExplanationRequest,
  EngineeringExplanationResponse,
  EvidenceChainNode,
  HumanActionItem,
  VerificationWorkspaceResponse,
  VerificationWorkspaceObligation,
  EvidenceRegisterRequest,
  VerificationCloseRequest,
  ActionCenterCategory,
  EngineeringActionItem,
  EngineeringActionCenterResponse,
  EngineeringActionCenterSummary,
} from "./cognitive_types";


interface CognitiveWorkspaceProps {
  projectId: string;
  systemId?: string | null;
  circuitId?: string | null;
  systemRevision?: number;
}

export const CognitiveWorkspace: React.FC<CognitiveWorkspaceProps> = ({
  projectId,
  systemId,
  circuitId,
  systemRevision = 1,
}) => {
  const [prompt, setPrompt] = useState("");
  const [isResolving, setIsResolving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isExplaining, setIsExplaining] = useState(false);

  // States
  const [intentPacket, setIntentPacket] = useState<EngineeringIntentPacket | null>(null);
  const [activePlan, setActivePlan] = useState<EngineeringTaskPlan | null>(null);
  const [contextSnapshot, setContextSnapshot] = useState<ContextSnapshot | null>(null);
  const [validationResult, setValidationResult] = useState<PlanValidationResult | null>(null);
  const [execution, setExecution] = useState<CognitiveExecution | null>(null);
  const [explanation, setExplanation] = useState<CognitiveExplanation | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Phase 2 Wave 2: Reflection & Reasoning States
  const [reflection, setReflection] = useState<EngineeringReflection | null>(null);
  const [isReflecting, setIsReflecting] = useState(false);
  const [isReplanning, setIsReplanning] = useState(false);
  const [replanSuccess, setReplanSuccess] = useState<string | null>(null);
  const [selectedFindingFilter, setSelectedFindingFilter] = useState<string>("ALL");

  // Phase 2 Wave 3: Decision Brief States
  const [decisionBrief, setDecisionBrief] = useState<EngineeringDecisionBrief | null>(null);
  const [isPreparingBrief, setIsPreparingBrief] = useState(false);
  const [isRecordingDecision, setIsRecordingDecision] = useState(false);
  const [decisionType, setDecisionType] = useState<HumanDecisionType>("ACCEPT_ALTERNATIVE");
  const [selectedAlternativeId, setSelectedAlternativeId] = useState<string>("");
  const [decisionRationale, setDecisionRationale] = useState<string>("");
  const [decisionActor, setDecisionActor] = useState<string>("Lead Systems Engineer");
  const [decisionResult, setDecisionResult] = useState<any>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // Phase 2 Wave 4: Engineering Memory States
  const [surfacedMemories, setSurfacedMemories] = useState<SurfacedMemoryItem[]>([]);
  const [isLoadingMemories, setIsLoadingMemories] = useState(false);
  const [memoryDomainFilter, setMemoryDomainFilter] = useState<string>("all");
  const [memoryFeedbackStatus, setMemoryFeedbackStatus] = useState<Record<string, string>>({});
  const [memoryError, setMemoryError] = useState<string | null>(null);

  const handleRetrieveMemories = async () => {
    setIsLoadingMemories(true);
    setMemoryError(null);
    try {
      const res = await apiClient.post(`/cognitive/projects/${projectId}/memories/retrieve`, {
        project_id: projectId,
        system_id: systemId || undefined,
        circuit_id: circuitId || undefined,
        engineering_domain: memoryDomainFilter !== "all" ? memoryDomainFilter : undefined,
      });
      const data = res.data?.data as MemoryRetrievalResponse;
      if (data && data.memories) {
        setSurfacedMemories(data.memories);
      }
    } catch (err: any) {
      setMemoryError(err?.response?.data?.detail?.message || err?.message || "Failed to retrieve contextual memories.");
    } finally {
      setIsLoadingMemories(false);
    }
  };

  const handleMemoryFeedback = async (memoryId: string, feedbackType: MemoryFeedbackType) => {
    try {
      await apiClient.post(`/cognitive/memories/${memoryId}/feedback`, {
        feedback_type: feedbackType,
        engineer_identity: "Human Engineer",
      });
      setMemoryFeedbackStatus((prev) => ({
        ...prev,
        [memoryId]: feedbackType,
      }));
    } catch (err: any) {
      console.error("Failed to submit feedback", err);
    }
  };

  // Phase 2 Wave 5: Engineering Context Synthesis States
  const [contextSynthesis, setContextSynthesis] = useState<EngineeringContextSnapshot | null>(null);
  const [isSynthesizingContext, setIsSynthesizingContext] = useState(false);
  const [includeHistoricalMemoryInContext, setIncludeHistoricalMemoryInContext] = useState(true);
  const [contextError, setContextError] = useState<string | null>(null);
  const [contextTab, setContextTab] = useState<"STATE" | "DETERMINISTIC" | "REQUIREMENTS" | "CONTRADICTIONS" | "HISTORY">("STATE");
  const [contextExplainQuery, setContextExplainQuery] = useState("");
  const [isExplainingContext, setIsExplainingContext] = useState(false);
  const [contextExplanation, setContextExplanation] = useState<ContextExplanationResponse | null>(null);
  const [contextExplainError, setContextExplainError] = useState<string | null>(null);

  const handleSynthesizeContext = async () => {
    setIsSynthesizingContext(true);
    setContextError(null);
    setContextExplanation(null);
    try {
      const res = await apiClient.post("/cognitive/context/synthesize", {
        project_id: projectId,
        system_id: systemId || undefined,
        circuit_id: circuitId || undefined,
        include_historical_memory: includeHistoricalMemoryInContext,
      });
      const data = res.data?.data as EngineeringContextSnapshot;
      if (data) {
        setContextSynthesis(data);
      }
    } catch (err: any) {
      setContextError(err?.response?.data?.detail?.message || err?.message || "Failed to synthesize engineering context snapshot.");
    } finally {
      setIsSynthesizingContext(false);
    }
  };

  const handleExplainContext = async () => {
    if (!contextSynthesis?.id || !contextExplainQuery.trim()) return;
    setIsExplainingContext(true);
    setContextExplainError(null);
    try {
      const res = await apiClient.post(`/cognitive/context/${contextSynthesis.id}/explain`, {
        user_query: contextExplainQuery,
      });
      const data = res.data?.data as ContextExplanationResponse;
      if (data) {
        setContextExplanation(data);
      }
    } catch (err: any) {
      setContextExplainError(err?.response?.data?.detail?.message || err?.message || "Failed to generate context explanation.");
    } finally {
      setIsExplainingContext(false);
    }
  };

  // Phase 2 Wave 6: Cognitive Engineering Workflow States
  const [workflow, setWorkflow] = useState<EngineeringCognitiveWorkflow | null>(null);
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [workflowPrompt, setWorkflowPrompt] = useState("");

  const handleStartWorkflow = async () => {
    const promptText = workflowPrompt.trim() || prompt.trim();
    if (!promptText) return;
    setIsStartingWorkflow(true);
    setWorkflowError(null);
    try {
      const res = await apiClient.post("/cognitive/workflows", {
        project_id: projectId,
        circuit_id: circuitId || undefined,
        system_id: systemId || undefined,
        user_request: promptText,
      });
      const data = res.data?.data as EngineeringCognitiveWorkflow;
      if (data) {
        setWorkflow(data);
      }
    } catch (err: any) {
      setWorkflowError(err?.response?.data?.detail?.message || err?.message || "Failed to start cognitive engineering workflow.");
    } finally {
      setIsStartingWorkflow(false);
    }
  };

  // Phase 2 Wave 7: Cognitive Interaction & Explainability States
  const [explainCategory, setExplainCategory] = useState<ExplanationCategory>("WHY");
  const [explainQuery, setExplainQuery] = useState("");
  const [explainTargetType, setExplainTargetType] = useState<string>("Requirement");
  const [explainTargetId, setExplainTargetId] = useState<string>("");
  const [isInterrogating, setIsInterrogating] = useState(false);
  const [interrogationResponse, setInterrogationResponse] = useState<EngineeringExplanationResponse | null>(null);
  const [interrogationError, setInterrogationError] = useState<string | null>(null);

  const handleInterrogate = async (categoryOverride?: ExplanationCategory) => {
    setIsInterrogating(true);
    setInterrogationError(null);
    const cat = categoryOverride || explainCategory;
    try {
      const payload: EngineeringExplanationRequest = {
        category: cat,
        user_query: explainQuery.trim() || undefined,
        target_entity_type: explainTargetType || undefined,
        target_entity_id: explainTargetId.trim() || undefined,
      };

      let res;
      if (workflow?.id) {
        res = await apiClient.post(`/cognitive/workflows/${workflow.id}/explain`, payload);
      } else if (contextSynthesis?.id) {
        res = await apiClient.post(`/cognitive/context/${contextSynthesis.id}/explain`, payload);
      } else {
        throw new Error("No active workflow or synthesized context snapshot available to interrogate.");
      }

      if (res.data?.data) {
        setInterrogationResponse(res.data.data as EngineeringExplanationResponse);
      }
    } catch (err: any) {
      console.error("Interrogation failed:", err);
      const detail = err.response?.data?.detail;
      setInterrogationError(typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message);
    } finally {
      setIsInterrogating(false);
    }
  };

  // Phase 2 Wave 8: Verification & Evidence Workspace States
  const [verificationWorkspace, setVerificationWorkspace] = useState<VerificationWorkspaceResponse | null>(null);
  const [isLoadingVerification, setIsLoadingVerification] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [selectedObligationId, setSelectedObligationId] = useState<string | null>(null);
  const [obligationDetail, setObligationDetail] = useState<VerificationWorkspaceObligation | null>(null);
  const [customVerificationWorkflowId, setCustomVerificationWorkflowId] = useState<string>("");

  // Evidence Form State
  const [evidenceType, setEvidenceType] = useState<string>("MEASUREMENT");
  const [evidenceSource, setEvidenceSource] = useState<string>("Bench Oscilloscope Rig 4");
  const [evidenceDesc, setEvidenceDesc] = useState<string>("");
  const [evidenceValue, setEvidenceValue] = useState<string>("");
  const [evidenceUnit, setEvidenceUnit] = useState<string>("");
  const [isPhysicalEvidence, setIsPhysicalEvidence] = useState<boolean>(true);
  const [evidenceInstrument, setEvidenceInstrument] = useState<string>("Tektronix MSO54");
  const [calibrationStatus, setCalibrationStatus] = useState<string>("CALIBRATED");
  const [isAttachingEvidence, setIsAttachingEvidence] = useState(false);
  const [evidenceSuccessMessage, setEvidenceSuccessMessage] = useState<string | null>(null);

  // Verification Closure Form State
  const [closeDecision, setCloseDecision] = useState<string>("VERIFIED");
  const [closeRationale, setCloseRationale] = useState<string>("");
  const [closeActor, setCloseActor] = useState<string>("Lead Hardware Engineer");
  const [closeWaiverReason, setCloseWaiverReason] = useState<string>("");
  const [isClosingVerification, setIsClosingVerification] = useState(false);
  const [closeSuccessMessage, setCloseSuccessMessage] = useState<string | null>(null);

  const handleLoadVerificationWorkspace = async (targetWorkflowId?: string) => {
    const wId = targetWorkflowId || customVerificationWorkflowId || workflow?.id;
    if (!wId) {
      setVerificationError("Please specify or execute a cognitive workflow first to inspect its verification workspace.");
      return;
    }
    setIsLoadingVerification(true);
    setVerificationError(null);
    try {
      const res = await apiClient.get(`/cognitive/workflows/${wId}/verification`);
      if (res.data?.data) {
        setVerificationWorkspace(res.data.data as VerificationWorkspaceResponse);
        if (res.data.data.obligations?.length > 0 && !selectedObligationId) {
          const first = res.data.data.obligations[0];
          setSelectedObligationId(first.verification_requirement_id);
          setObligationDetail(first);
        }
      }
    } catch (err: any) {
      console.error("Failed to load verification workspace:", err);
      const detail = err.response?.data?.detail;
      setVerificationError(typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message);
    } finally {
      setIsLoadingVerification(false);
    }
  };

  const handleSelectObligation = async (oblId: string) => {
    setSelectedObligationId(oblId);
    setVerificationError(null);
    setEvidenceSuccessMessage(null);
    setCloseSuccessMessage(null);
    try {
      const res = await apiClient.get(`/cognitive/verification/${oblId}`);
      if (res.data?.data) {
        setObligationDetail(res.data.data as VerificationWorkspaceObligation);
      }
    } catch (err: any) {
      console.error("Failed to fetch obligation detail:", err);
    }
  };

  const handleAttachEvidence = async () => {
    if (!selectedObligationId) return;
    if (!evidenceDesc.trim()) {
      setVerificationError("Evidence description is mandatory.");
      return;
    }
    setIsAttachingEvidence(true);
    setVerificationError(null);
    setEvidenceSuccessMessage(null);
    try {
      const payload: EvidenceRegisterRequest = {
        evidence_type: evidenceType,
        source: evidenceSource,
        description: evidenceDesc,
        value: evidenceValue || undefined,
        unit: evidenceUnit || undefined,
        is_physical: isPhysicalEvidence,
        instrument: evidenceInstrument || undefined,
        calibration_status: calibrationStatus || undefined,
      };
      await apiClient.post(`/cognitive/verification/${selectedObligationId}/evidence`, payload);
      setEvidenceSuccessMessage("Physical evidence attached with cryptographic SHA-256 integrity.");
      setEvidenceDesc("");
      setEvidenceValue("");
      // Refresh obligation and workspace
      await handleSelectObligation(selectedObligationId);
      if (workflow?.id || customVerificationWorkflowId) {
        await handleLoadVerificationWorkspace();
      }
    } catch (err: any) {
      console.error("Failed to attach evidence:", err);
      const detail = err.response?.data?.detail;
      setVerificationError(typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message);
    } finally {
      setIsAttachingEvidence(false);
    }
  };

  const handleCloseVerification = async () => {
    if (!selectedObligationId) return;
    if (!closeRationale.trim()) {
      setVerificationError("Human rationale is strictly mandatory to close verification.");
      return;
    }
    setIsClosingVerification(true);
    setVerificationError(null);
    setCloseSuccessMessage(null);
    try {
      const payload: VerificationCloseRequest = {
        decision: closeDecision,
        rationale: closeRationale,
        actor: closeActor,
        waiver_reason: closeDecision === "WAIVED" ? closeWaiverReason : undefined,
        current_revision: systemRevision,
      };
      await apiClient.post(`/cognitive/verification/${selectedObligationId}/close`, payload);
      setCloseSuccessMessage(`Verification obligation closed with decision: ${closeDecision}`);
      setCloseRationale("");
      setCloseWaiverReason("");
      // Refresh obligation and workspace
      await handleSelectObligation(selectedObligationId);
      if (workflow?.id || customVerificationWorkflowId) {
        await handleLoadVerificationWorkspace();
      }
    } catch (err: any) {
      console.error("Failed to close verification obligation:", err);
      const detail = err.response?.data?.detail;
      setVerificationError(typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message);
    } finally {
      setIsClosingVerification(false);
    }
  };

  // Phase 2 Wave 9: Action & Closure Center States
  const [actionCenter, setActionCenter] = useState<EngineeringActionCenterResponse | null>(null);
  const [isLoadingActions, setIsLoadingActions] = useState(false);
  const [actionCenterError, setActionCenterError] = useState<string | null>(null);
  const [selectedActionCategory, setSelectedActionCategory] = useState<ActionCenterCategory>("ALL");
  const [selectedActionItem, setSelectedActionItem] = useState<EngineeringActionItem | null>(null);
  const [actionExplanation, setActionExplanation] = useState<EngineeringExplanationResponse | null>(null);
  const [isExplainingAction, setIsExplainingAction] = useState(false);
  const [actionExplainError, setActionExplainError] = useState<string | null>(null);

  const handleLoadActionCenter = async (categoryOverride?: ActionCenterCategory) => {
    setIsLoadingActions(true);
    setActionCenterError(null);
    const cat = categoryOverride || selectedActionCategory;
    try {
      const params: any = {};
      if (cat !== "ALL") params.category = cat;
      if (circuitId) params.circuit_id = circuitId;
      if (systemId) params.system_id = systemId;
      const res = await apiClient.get(`/cognitive/projects/${projectId}/actions`, { params });
      if (res.data?.data) {
        setActionCenter(res.data.data as EngineeringActionCenterResponse);
        if (res.data.data.actions?.length > 0 && !selectedActionItem) {
          setSelectedActionItem(res.data.data.actions[0]);
        }
      }
    } catch (err: any) {
      console.error("Failed to load Action Center:", err);
      const detail = err.response?.data?.detail;
      setActionCenterError(typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message);
    } finally {
      setIsLoadingActions(false);
    }
  };

  const handleExplainActionItem = async (action: EngineeringActionItem) => {
    setIsExplainingAction(true);
    setActionExplainError(null);
    try {
      const res = await apiClient.post(
        `/cognitive/actions/${action.source_entity_type}/${action.source_entity_id}/explain`,
        { category: "WHY" }
      );
      if (res.data?.data) {
        setActionExplanation(res.data.data as EngineeringExplanationResponse);
      }
    } catch (err: any) {
      console.error("Failed to explain action item:", err);
      const detail = err.response?.data?.detail;
      setActionExplainError(typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message);
    } finally {
      setIsExplainingAction(false);
    }
  };

  // Ambiguity selection
  const [selectedDisambiguation, setSelectedDisambiguation] = useState<{ [target: string]: string }>({});


  const presetPrompts = [
    "Verify thermal margins and electrical stress for power converters under 85°C ambient.",
    "Evaluate failure propagation and identify single points of failure across subsystems.",
    "Analyze system requirement coverage and identify missing verification evidence.",
    "Investigate active critical findings and check design review gating readiness.",
  ];

  // 1. Resolve raw prompt into structured IntentPacket
  const handleResolveIntent = async (customPrompt?: string) => {
    const rawText = customPrompt || prompt;
    if (!rawText.trim()) return;

    setIsResolving(true);
    setErrorMessage(null);
    setExecution(null);
    setExplanation(null);
    setReflection(null);
    setReplanSuccess(null);
    setActivePlan(null);
    setContextSnapshot(null);
    setValidationResult(null);

    try {
      const res = await apiClient.post("/cognitive/intents/resolve", {
        raw_request: rawText,
        project_id: projectId,
        system_id: systemId || undefined,
        circuit_id: circuitId || undefined,
        scope: systemId ? "SYSTEM" : "CIRCUIT",
      });

      const packet = res.data?.data as EngineeringIntentPacket;
      setIntentPacket(packet);

      // Automatically generate plan if clarification is not blocked
      if (packet && packet.status !== "CLARIFICATION_REQUIRED" && packet.status !== "PLANNING_BLOCKED") {
        await handleGeneratePlan(packet.id);
      }
    } catch (err: any) {
      console.error("Intent resolution failed:", err);
      setErrorMessage(err.response?.data?.detail || "Failed to resolve engineering intent.");
    } finally {
      setIsResolving(false);
    }
  };

  // 2. Generate task plan DAG
  const handleGeneratePlan = async (packetId: string) => {
    try {
      const planRes = await apiClient.post("/cognitive/plans", {
        intent_packet_id: packetId,
        execution_policy: { read_only_mode: true },
      });
      const plan = planRes.data?.data as EngineeringTaskPlan;
      setActivePlan(plan);

      // Fetch bound context snapshot if available
      if (plan.context_snapshot_id) {
        try {
          const snapRes = await apiClient.get(`/cognitive/snapshots/${plan.context_snapshot_id}`);
          if (snapRes.data?.data) {
            setContextSnapshot(snapRes.data.data as ContextSnapshot);
          }
        } catch (snapErr) {
          console.error("Failed to load context snapshot:", snapErr);
        }
      }

      // Validate plan
      await handleValidatePlan(plan.id);
    } catch (err: any) {
      console.error("Plan creation failed:", err);
      setErrorMessage(err.response?.data?.detail || "Failed to generate task plan.");
    }
  };

  // 3. Validate plan across 5 dimensions
  const handleValidatePlan = async (planId: string) => {
    setIsValidating(true);
    try {
      const valRes = await apiClient.post(`/cognitive/plans/${planId}/validate`);
      const val = valRes.data?.data as PlanValidationResult;
      setValidationResult(val);
    } catch (err: any) {
      console.error("Plan validation failed:", err);
    } finally {
      setIsValidating(false);
    }
  };

  // 4. Execute deterministic plan (read-only)
  const handleExecutePlan = async () => {
    if (!activePlan) return;
    setIsExecuting(true);
    setErrorMessage(null);

    try {
      const execRes = await apiClient.post(`/cognitive/plans/${activePlan.id}/execute`, {
        force_revalidation: false,
      });
      const execData = execRes.data?.data as CognitiveExecution;
      setExecution(execData);

      // Request explanation
      await handleFetchExplanation(execData.id);

      // Trigger Cognitive Reflection & Reasoning
      await handleTriggerReflection(execData.id);
    } catch (err: any) {
      console.error("Plan execution failed:", err);
      if (err.response?.status === 409) {
        setErrorMessage("COGNITIVE_PLAN_STALE: Base revision mismatch. System architecture has been updated. Please re-generate plan.");
      } else {
        setErrorMessage(err.response?.data?.detail?.message || "Execution halted.");
      }
    } finally {
      setIsExecuting(false);
    }
  };

  // 5. Fetch AI explanation with provenance trace
  const handleFetchExplanation = async (execId: string) => {
    setIsExplaining(true);
    try {
      const expRes = await apiClient.post("/cognitive/explanations", {
        execution_id: execId,
        user_query: "Interpret findings and verification obligations.",
      });
      setExplanation(expRes.data?.data as CognitiveExplanation);
    } catch (err) {
      console.error("Failed to generate explanation:", err);
    } finally {
      setIsExplaining(false);
    }
  };

  // 6. Trigger Cognitive Reflection & Engineering Reasoning
  const handleTriggerReflection = async (execId?: string) => {
    const targetExecId = execId || execution?.id;
    if (!targetExecId) return;

    setIsReflecting(true);
    setErrorMessage(null);
    setReplanSuccess(null);

    try {
      const reflRes = await apiClient.post(`/cognitive/executions/${targetExecId}/reflect`, {
        user_focus: "Evaluate contradictions, unknowns, requirements, and verification obligations.",
        force_reevaluation: true,
      });
      const refl = reflRes.data?.data as EngineeringReflection;
      setReflection(refl);
    } catch (err: any) {
      console.error("Cognitive reflection failed:", err);
      setErrorMessage(err.response?.data?.detail || "Cognitive reflection failed.");
    } finally {
      setIsReflecting(false);
    }
  };

  // 7. Bounded Re-planning from Reflection Findings
  const handleReplanFromReflection = async () => {
    if (!reflection) return;

    setIsReplanning(true);
    setErrorMessage(null);
    setReplanSuccess(null);

    try {
      const replanRes = await apiClient.post(`/cognitive/reflections/${reflection.id}/replan`, {
        execution_policy: {
          read_only_mode: true,
          reflection_cycle: reflection.reflection_cycle + 1,
        },
      });
      const replanResult = replanRes.data?.data as ReflectionReplanResult;
      setReplanSuccess(
        `Follow-up task plan successfully synthesized (Cycle ${replanResult.reflection_cycle} of 3) with ${replanResult.tasks_count} targeted task(s).`
      );

      // Load new follow-up plan
      const newPlanRes = await apiClient.get(`/cognitive/plans/${replanResult.follow_up_plan_id}`);
      if (newPlanRes.data?.data) {
        const newPlan = newPlanRes.data.data as EngineeringTaskPlan;
        setActivePlan(newPlan);
        await handleValidatePlan(newPlan.id);
      }
    } catch (err: any) {
      console.error("Re-planning failed:", err);
      if (err.response?.data?.detail?.code === "MAX_REFLECTION_CYCLES_REACHED") {
        setErrorMessage(
          err.response.data.detail.message || "MAX_REFLECTION_CYCLES_REACHED: Hard iteration limit reached."
        );
      } else {
        setErrorMessage(err.response?.data?.detail || "Failed to formulate follow-up plan.");
      }
    } finally {
      setIsReplanning(false);
    }
  };

  // Phase 2 Wave 3: Prepare Decision Brief
  const handlePrepareDecisionBrief = async () => {
    setIsPreparingBrief(true);
    setDecisionError(null);
    try {
      const payload: any = {
        project_id: projectId,
        system_id: systemId || undefined,
        circuit_id: circuitId || undefined,
        question: intentPacket?.goal || prompt || "Engineering Decision Brief",
        reflection_id: reflection?.id || undefined,
        context_snapshot_id: contextSnapshot?.id || undefined,
      };

      const res = await apiClient.post(
        "/cognitive/decision-briefs",
        payload
      );
      if (res.data?.data) {
        setDecisionBrief(res.data.data as EngineeringDecisionBrief);
        if (res.data.data.alternative_ids?.length > 0) {
          setSelectedAlternativeId(res.data.data.alternative_ids[0]);
        }
      }
    } catch (err: any) {
      console.error("Failed to prepare decision brief:", err);
      const detail = err.response?.data?.detail;
      setDecisionError(
        typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message
      );
    } finally {
      setIsPreparingBrief(false);
    }
  };

  // Phase 2 Wave 3: Record Human Decision
  const handleRecordHumanDecision = async () => {
    if (!decisionBrief) return;
    setIsRecordingDecision(true);
    setDecisionError(null);
    try {
      const payload = {
        decision_type: decisionType,
        selected_alternative_id:
          decisionType === "ACCEPT_ALTERNATIVE" || decisionType === "ADOPT_ALTERNATIVE"
            ? selectedAlternativeId
            : undefined,
        rationale: decisionRationale || "Formal human engineering review and ratification.",
        actor: decisionActor,
        current_revision: systemRevision,
      };

      const res = await apiClient.post(
        `/cognitive/decision-briefs/${decisionBrief.id}/decision`,
        payload
      );
      if (res.data?.data) {
        setDecisionBrief(res.data.data as EngineeringDecisionBrief);
        setDecisionResult(res.data.data.decision_record || res.data.data);
      }
    } catch (err: any) {
      console.error("Failed to record human decision:", err);
      const detail = err.response?.data?.detail;
      setDecisionError(
        typeof detail === "object" ? detail.message || JSON.stringify(detail) : detail || err.message
      );
    } finally {
      setIsRecordingDecision(false);
    }
  };

  // Disambiguation confirmation
  const handleConfirmDisambiguation = (ambiguity: IntentAmbiguity, refDes: string) => {
    setSelectedDisambiguation((prev) => ({ ...prev, [ambiguity.target]: refDes }));
    // Append ref_des and re-resolve
    const updatedPrompt = `${prompt} specifically focusing on ${refDes}.`;
    setPrompt(updatedPrompt);
    handleResolveIntent(updatedPrompt);
  };

  const isStale = Boolean(activePlan && activePlan.base_revision !== systemRevision);

  return (
    <div className="flex-1 flex flex-col bg-zinc-950 text-zinc-100 overflow-y-auto">
      {/* Top Workspace Header */}
      <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-900/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-sky-950/60 border border-sky-800/80 rounded-lg text-sky-400">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold tracking-wide text-zinc-100 uppercase">
                Cognitive Engineering Planner & Intent Orchestrator
              </h2>
              <Badge variant="outline" className="text-[10px] font-mono text-sky-400 border-sky-800">
                Phase 2 Wave 1
              </Badge>
            </div>
            <p className="text-xs text-zinc-400">
              Deterministic task DAG generation, context binding, and verifiable capability execution
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-xs font-mono text-zinc-300 border-zinc-700 bg-zinc-900">
            <GitBranch className="w-3.5 h-3.5 mr-1 text-sky-400" />
            System Rev. {systemRevision}
          </Badge>
          <Badge variant="outline" className="text-xs font-mono text-emerald-400 border-emerald-800 bg-emerald-950/30">
            <Shield className="w-3.5 h-3.5 mr-1 text-emerald-400" />
            Read-Only Guard Active
          </Badge>
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-7xl mx-auto w-full">
        {/* Error Alert */}
        {errorMessage && (
          <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-lg flex items-start gap-3 text-rose-200">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="text-xs leading-relaxed">
              <span className="font-semibold block mb-0.5">Execution Alert</span>
              {errorMessage}
            </div>
          </div>
        )}

        {/* 1. Natural Language Intent Input */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-sky-400" />
              <h3 className="text-sm font-medium text-zinc-200">Engineering Intent Input</h3>
            </div>
            <span className="text-[11px] text-zinc-500 font-mono">
              Natural Language → Controlled Engineering IntentPacket
            </span>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Verify thermal margin for U1 buck converter under 12V input and 85C ambient temperature..."
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-sky-600 font-sans"
              onKeyDown={(e) => e.key === "Enter" && handleResolveIntent()}
            />
            <Button
              onClick={() => handleResolveIntent()}
              disabled={isResolving || !prompt.trim()}
              className="bg-sky-600 hover:bg-sky-500 text-white font-medium px-5 flex items-center gap-2"
            >
              {isResolving ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Resolving...
                </>
              ) : (
                <>
                  <Compass className="w-4 h-4" />
                  Resolve Intent
                </>
              )}
            </Button>
          </div>

          {/* Quick Presets */}
          <div className="space-y-1.5 pt-1">
            <span className="text-[11px] text-zinc-500 font-medium">Engineering Scenarios:</span>
            <div className="flex flex-wrap gap-1.5">
              {presetPrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setPrompt(p);
                    handleResolveIntent(p);
                  }}
                  className="text-xs text-zinc-400 hover:text-sky-300 bg-zinc-950 hover:bg-zinc-800 border border-zinc-800/80 rounded px-2.5 py-1 text-left transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 2. Disambiguation / Clarification Card (if triggered) */}
        {intentPacket && intentPacket.status === "CLARIFICATION_REQUIRED" && (
          <div className="bg-amber-950/30 border border-amber-800/60 rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2 text-amber-300 font-medium text-sm">
              <HelpCircle className="w-4 h-4" />
              <span>Clarification Required — Disambiguate Component Selection</span>
            </div>
            <p className="text-xs text-zinc-300">
              Multiple physical components matched your request. Please select which component you wish to evaluate before planning proceeds:
            </p>

            <div className="space-y-3 pt-2">
              {intentPacket.ambiguities.map((amb, i) => (
                <div key={i} className="p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg space-y-2">
                  <div className="text-xs font-mono text-zinc-300">{amb.reason}</div>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {(amb.candidates || []).map((cand) => (
                      <Button
                        key={cand.ref_des}
                        variant="outline"
                        size="sm"
                        onClick={() => handleConfirmDisambiguation(amb, cand.ref_des)}
                        className="text-xs border-amber-700/60 text-amber-200 hover:bg-amber-900/40 font-mono"
                      >
                        Target: {cand.ref_des} ({cand.name || "IC"})
                      </Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 3. Resolved Intent Packet Inspector */}
        {intentPacket && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Packet Summary */}
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Intent Classification
                </span>
                <Badge
                  variant="outline"
                  className="text-[10px] font-mono text-sky-400 border-sky-800 bg-sky-950/40"
                >
                  {intentPacket.intent_type}
                </Badge>
              </div>

              <div className="text-xs text-zinc-200">
                <span className="text-zinc-500 block text-[10px] uppercase">Goal</span>
                {intentPacket.goal}
              </div>

              <div className="flex items-center justify-between text-xs pt-1 border-t border-zinc-800/80">
                <span className="text-zinc-500">Interpretation Confidence:</span>
                <span className="font-mono text-sky-400 font-medium">
                  {Math.round(intentPacket.context_confidence * 100)}%
                </span>
              </div>
            </div>

            {/* Extracted Entities */}
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4 space-y-3">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
                Extracted Entities & Parameters
              </span>
              {intentPacket.entities.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {intentPacket.entities.map((e, idx) => (
                    <Badge
                      key={idx}
                      variant="secondary"
                      className="text-[11px] font-mono bg-zinc-800 text-zinc-200 border border-zinc-700"
                    >
                      {e.type}: {e.value ? `${e.value}${e.unit || ""}` : e.ref_des || e.raw}
                    </Badge>
                  ))}
                </div>
              ) : (
                <span className="text-xs text-zinc-500 italic">No explicit parameters extracted.</span>
              )}
            </div>

            {/* Inferred Constraints & Assumptions */}
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4 space-y-3">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
                Bound Constraints & Scenarios
              </span>
              <div className="space-y-1 text-xs">
                {intentPacket.constraints.length > 0 && (
                  <div className="text-amber-400 font-mono text-[11px]">
                    Constraints: {intentPacket.constraints.length} detected
                  </div>
                )}
                {intentPacket.scenarios.length > 0 && (
                  <div className="text-purple-400 font-mono text-[11px]">
                    Scenarios: {intentPacket.scenarios.length} active
                  </div>
                )}
                {intentPacket.assumptions.length > 0 && (
                  <div className="text-sky-400 font-mono text-[11px]">
                    Assumptions: {intentPacket.assumptions.length} verified
                  </div>
                )}
                {intentPacket.constraints.length === 0 &&
                  intentPacket.scenarios.length === 0 &&
                  intentPacket.assumptions.length === 0 && (
                    <span className="text-xs text-zinc-500 italic">Default nominal conditions assumed.</span>
                  )}
              </div>
            </div>
          </div>
        )}

        {/* 4. Task Plan DAG & Validation Panel */}
        {activePlan && (
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <ListOrdered className="w-4 h-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-zinc-200">
                  Engineering Task Plan (Directed Acyclic Graph)
                </h3>
              </div>

              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className={`text-[10px] font-mono ${
                    activePlan.status === "COMPLETED"
                      ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                      : activePlan.status === "PARTIAL"
                      ? "text-amber-400 border-amber-800 bg-amber-950/40"
                      : activePlan.status === "STALE" || isStale
                      ? "text-rose-400 border-rose-800 bg-rose-950/40"
                      : activePlan.status === "EXECUTING"
                      ? "text-sky-400 border-sky-800 bg-sky-950/40 animate-pulse"
                      : "text-zinc-300 border-zinc-700 bg-zinc-900"
                  }`}
                >
                  STATUS: {isStale ? "STALE" : activePlan.status}
                </Badge>

                <Badge
                  variant="outline"
                  className="text-[10px] font-mono text-zinc-300 border-zinc-700 bg-zinc-900"
                >
                  Rev. {activePlan.base_revision}
                </Badge>

                {validationResult && (
                  <Badge
                    variant="outline"
                    className={`text-[10px] font-mono ${
                      validationResult.is_valid
                        ? "text-emerald-400 border-emerald-800"
                        : "text-amber-400 border-amber-800"
                    }`}
                  >
                    {validationResult.is_valid ? "DAG & POLICIES VERIFIED" : "VALIDATION BLOCKED"}
                  </Badge>
                )}
              </div>
            </div>

            {/* Canonical Context Snapshot Banner */}
            {contextSnapshot && (
              <div className="p-3.5 bg-zinc-950/90 border border-zinc-800 rounded-lg space-y-2 text-xs">
                <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                  <div className="flex items-center gap-2 text-sky-400 font-medium">
                    <Shield className="w-3.5 h-3.5" />
                    <span>Canonical Context Snapshot & Integrity Digest</span>
                  </div>
                  <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                    Rule Set {contextSnapshot.rule_set_version}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] font-mono text-zinc-400 pt-1">
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase">Project Rev</span>
                    <span className="text-zinc-200">v{contextSnapshot.project_revision}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase">System Rev</span>
                    <span className="text-zinc-200">{contextSnapshot.system_revision !== null ? `v${contextSnapshot.system_revision}` : "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase">Circuit Rev</span>
                    <span className="text-zinc-200">{contextSnapshot.circuit_revision !== null ? `v${contextSnapshot.circuit_revision}` : "N/A"}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-[10px] uppercase">Snapshot ID</span>
                    <span className="text-zinc-300 truncate block">{contextSnapshot.id.substring(0, 12)}...</span>
                  </div>
                </div>
                <div className="pt-1 flex items-center justify-between bg-zinc-900/60 p-2 rounded border border-zinc-800/60 font-mono text-[10px]">
                  <span className="text-zinc-500">SHA-256 Digest:</span>
                  <span className="text-emerald-400 font-semibold">{contextSnapshot.context_digest}</span>
                </div>
              </div>
            )}

            {/* Stale Warning Banner */}
            {isStale && (
              <div className="p-3 bg-rose-950/30 border border-rose-800/60 rounded-lg flex items-center justify-between text-xs text-rose-300">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span>
                    The engineering system has advanced to Rev. {systemRevision} since this plan was created (Rev. {activePlan.base_revision}).
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleResolveIntent()}
                  className="text-xs border-rose-700 hover:bg-rose-900/40 text-rose-200"
                >
                  Regenerate Plan
                </Button>
              </div>
            )}

            {/* Task Cards */}
            <div className="space-y-2 pt-1">
              {(activePlan.tasks || []).map((t, index) => (
                <div
                  key={t.id || index}
                  className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-lg flex items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-zinc-800 text-zinc-300 font-mono text-xs flex items-center justify-center font-medium">
                      {t.order_index + 1}
                    </span>
                    <div>
                      <div className="text-xs font-semibold text-zinc-200 flex items-center gap-2">
                        {t.description}
                        <Badge variant="outline" className="text-[9px] font-mono border-zinc-700 text-zinc-400">
                          {t.task_type}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
                        Required Capabilities: {t.required_capabilities.join(", ") || "none"}
                        {t.dependencies && t.dependencies.length > 0 && (
                          <span className="ml-2 text-sky-400">Depends on: {t.dependencies.join(", ")}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <Badge
                    variant="outline"
                    className={`text-[10px] font-mono ${
                      t.status === "COMPLETED"
                        ? "text-emerald-400 border-emerald-800"
                        : t.status === "RUNNING"
                        ? "text-sky-400 border-sky-800 animate-pulse"
                        : "text-zinc-500 border-zinc-800"
                    }`}
                  >
                    {t.status}
                  </Badge>
                </div>
              ))}
            </div>

            {/* Execute Button */}
            <div className="pt-2 flex justify-end">
              <Button
                onClick={handleExecutePlan}
                disabled={isExecuting || isStale || Boolean(validationResult && !validationResult.is_valid)}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-5 flex items-center gap-2"
              >
                {isExecuting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Executing Deterministic Capabilities...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    Execute Deterministic Plan
                  </>
                )}
              </Button>
            </div>
          </div>
        )}

        {/* 5. Execution Results & Findings */}
        {execution && (
          <div className="space-y-6">
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold text-zinc-200">Deterministic Execution Output</h3>
                </div>
                <Badge
                  variant="outline"
                  className={`text-[10px] font-mono ${
                    execution.execution_status === "SUCCESS"
                      ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                      : execution.execution_status === "PARTIAL"
                      ? "text-amber-400 border-amber-800 bg-amber-950/40"
                      : "text-rose-400 border-rose-800 bg-rose-950/40"
                  }`}
                >
                  EXECUTION {execution.execution_status}
                </Badge>
              </div>

              {/* Partial / Failed Execution Breakdown Banner */}
              {(execution.execution_status === "PARTIAL" || execution.execution_status === "FAILED") && (
                <div className="p-4 bg-amber-950/30 border border-amber-800/60 rounded-lg space-y-2 text-xs">
                  <div className="flex items-center gap-2 text-amber-300 font-semibold">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span>
                      {execution.execution_status === "PARTIAL" ? "Partial Execution: Upstream Task Blocked" : "Execution Halted"}
                    </span>
                  </div>
                  {execution.blocking_reasons && execution.blocking_reasons.length > 0 && (
                    <div className="space-y-1 text-zinc-300 font-mono text-[11px] bg-zinc-950 p-2.5 rounded border border-amber-900/40">
                      {execution.blocking_reasons.map((r, i) => (
                        <div key={i} className="text-amber-200">
                          • {r}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Strict Epistemological Boundary Alert */}
              <div className="p-3 bg-zinc-950 border border-sky-900/60 rounded-lg flex items-start gap-3">
                <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                <div className="text-xs text-zinc-300 leading-relaxed">
                  <span className="font-semibold text-sky-300 block">Authoritative Epistemological Rule:</span>
                  <span className="font-mono text-zinc-200">UNKNOWN != PASS</span>. Unmeasured margins or unverified requirements remain explicitly flagged as UNKNOWN. AI does not synthesize scores or grant approval.
                </div>
              </div>

              {/* Execution Results Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Findings List */}
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                      Authoritative Findings ({execution.findings.length})
                    </span>
                    <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                      Deterministic
                    </Badge>
                  </div>
                  {execution.findings.length > 0 ? (
                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                      {execution.findings.map((f, i) => (
                        <div key={i} className="p-2.5 bg-zinc-900/80 border border-zinc-800 rounded text-xs space-y-1">
                          <div className="flex items-center justify-between font-mono text-[11px]">
                            <span className="text-zinc-200 font-semibold">{f.category || "FINDING"}</span>
                            <Badge
                              variant="outline"
                              className={`text-[9px] ${
                                f.severity === "CRITICAL"
                                  ? "text-rose-400 border-rose-800"
                                  : "text-amber-400 border-amber-800"
                              }`}
                            >
                              {f.severity || "WARNING"}
                            </Badge>
                          </div>
                          <p className="text-zinc-400 text-[11px]">{f.description || f.message}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-emerald-400 flex items-center gap-1.5 py-4">
                      <CheckCircle2 className="w-4 h-4" />
                      No rule violations or critical anomalies detected.
                    </div>
                  )}
                </div>

                {/* Explicit Unknowns & Gaps */}
                <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                      Explicit Unknowns & Evidence Gaps ({execution.unknowns.length})
                    </span>
                    <Badge variant="outline" className="text-[10px] border-amber-800 text-amber-400">
                      Non-Assumed
                    </Badge>
                  </div>
                  {execution.unknowns.length > 0 ? (
                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                      {execution.unknowns.map((u, i) => (
                        <div key={i} className="p-2.5 bg-amber-950/20 border border-amber-900/40 rounded text-xs space-y-0.5">
                          <span className="font-mono text-[11px] text-amber-300 block font-medium">
                            Source: {u.source || "Deterministic Engine"}
                          </span>
                          <p className="text-zinc-300 text-[11px]">
                            {typeof u.unknown === "string" ? u.unknown : JSON.stringify(u.unknown || u)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-zinc-500 italic py-4">
                      No missing parameters or unverified requirement gaps.
                    </div>
                  )}
                </div>
              </div>

              {/* Human Actions Required */}
              {execution.human_actions_required && execution.human_actions_required.length > 0 && (
                <div className="p-4 bg-purple-950/20 border border-purple-900/40 rounded-lg space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-purple-300 uppercase">
                    <CheckSquare className="w-4 h-4 text-purple-400" />
                    Human Engineer Verification Obligations
                  </div>
                  <ul className="space-y-1 text-xs text-zinc-300">
                    {execution.human_actions_required.map((act, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-purple-400 font-mono">•</span>
                        {act}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* 6. AI Explanation & Provenance Box */}
            {explanation && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-sky-400" />
                    <span className="text-xs font-bold text-sky-400 tracking-wider uppercase">
                      ORIGIN: AI_GENERATED (INFORMATIONAL ONLY)
                    </span>
                  </div>
                  <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                    Authority: {explanation.authority}
                  </Badge>
                </div>

                <div className="text-xs text-zinc-300 leading-relaxed font-sans whitespace-pre-line bg-zinc-950 p-4 rounded-lg border border-zinc-800/80">
                  {explanation.explanation}
                </div>

                {/* Execution Provenance & Integrity Digest */}
                {execution.provenance && (
                  <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-400 space-y-1.5">
                    <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] font-sans pb-1 border-b border-zinc-800/60">
                      <span className="font-semibold text-zinc-300">Execution Provenance & Integrity Digest</span>
                      <span className="text-emerald-400">SHA-256 Verified</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Model:</span>
                      <span className="text-zinc-200">{execution.provenance.model_identifier}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Prompt / Rule:</span>
                      <span className="text-zinc-200">{execution.provenance.prompt_id || "intent_resolver"}:{execution.provenance.prompt_version} (Rules {execution.provenance.rule_set_version || "v1.0.0"})</span>
                    </div>
                    {execution.provenance.context_snapshot_id && (
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Context Snapshot:</span>
                        <span className="text-zinc-300 font-mono text-[10px]">{execution.provenance.context_snapshot_id}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Input Digest:</span>
                      <span className="text-zinc-300 font-mono text-[10px]">
                        {execution.provenance.input_digest}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Output Digest:</span>
                      <span className="text-zinc-300 font-mono text-[10px]">
                        {execution.provenance.output_digest}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 7. Cognitive Reflection & Engineering Reasoning (Phase 2 Wave 2) */}
            {execution && (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-6">
                {/* Reflection Header */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Scale className="w-5 h-5 text-indigo-400" />
                      <h3 className="text-sm font-semibold tracking-wide text-zinc-100 uppercase">
                        Cognitive Reflection & Engineering Reasoning
                      </h3>
                      <Badge variant="outline" className="text-[10px] font-mono text-indigo-400 border-indigo-800">
                        Phase 2 Wave 2
                      </Badge>
                    </div>
                    <p className="text-xs text-zinc-400">
                      Evaluates contradictions, uncharacterized unknowns, evidence currency, and verification gaps.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {reflection && (
                      <Badge
                        variant="outline"
                        className={`text-xs font-mono ${
                          reflection.status === "COMPLETE"
                            ? "text-emerald-400 border-emerald-800 bg-emerald-950/30"
                            : reflection.status === "ADDITIONAL_WORK_REQUIRED"
                            ? "text-amber-400 border-amber-800 bg-amber-950/30"
                            : "text-red-400 border-red-800 bg-red-950/30"
                        }`}
                      >
                        {reflection.status} • Cycle {reflection.reflection_cycle} of 3
                      </Badge>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleTriggerReflection()}
                      disabled={isReflecting}
                      className="border-indigo-800/80 bg-indigo-950/30 hover:bg-indigo-900/50 text-indigo-300 text-xs gap-1.5"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isReflecting ? "animate-spin" : ""}`} />
                      {reflection ? "Re-evaluate Reflection" : "Run Cognitive Reflection"}
                    </Button>
                  </div>
                </div>

                {/* Epistemic Invariants Strip */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px] font-mono text-zinc-400">
                  <div className="p-2 bg-zinc-950/80 border border-zinc-800/80 rounded flex items-center gap-1.5">
                    <Lock className="w-3 h-3 text-sky-400" />
                    <span>AI AUTHORITY = NONE</span>
                  </div>
                  <div className="p-2 bg-zinc-950/80 border border-zinc-800/80 rounded flex items-center gap-1.5">
                    <Shield className="w-3 h-3 text-amber-400" />
                    <span>UNKNOWN != SATISFIED</span>
                  </div>
                  <div className="p-2 bg-zinc-950/80 border border-zinc-800/80 rounded flex items-center gap-1.5">
                    <CheckSquare className="w-3 h-3 text-purple-400" />
                    <span>CALCULATED != VERIFIED</span>
                  </div>
                  <div className="p-2 bg-zinc-950/80 border border-zinc-800/80 rounded flex items-center gap-1.5">
                    <FileText className="w-3 h-3 text-emerald-400" />
                    <span>ANALYSIS != PHYSICAL</span>
                  </div>
                </div>

                {reflection ? (
                  <div className="space-y-6">
                    {/* Discrete Fact Gap Counters (Zero Synthetic Scoring) */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                      <div className={`p-3 rounded-lg border ${reflection.has_contradictions ? "bg-red-950/20 border-red-900/60" : "bg-zinc-950 border-zinc-800"}`}>
                        <span className="text-[10px] text-zinc-400 uppercase font-medium block">Contradictions</span>
                        <span className={`text-base font-bold font-mono ${reflection.has_contradictions ? "text-red-400" : "text-emerald-400"}`}>
                          {reflection.has_contradictions ? "DETECTED" : "NONE"}
                        </span>
                      </div>

                      <div className={`p-3 rounded-lg border ${reflection.has_unresolved_unknowns ? "bg-amber-950/20 border-amber-900/60" : "bg-zinc-950 border-zinc-800"}`}>
                        <span className="text-[10px] text-zinc-400 uppercase font-medium block">Explicit Unknowns</span>
                        <span className={`text-base font-bold font-mono ${reflection.has_unresolved_unknowns ? "text-amber-400" : "text-emerald-400"}`}>
                          {reflection.has_unresolved_unknowns ? "PRESENT" : "RESOLVED"}
                        </span>
                      </div>

                      <div className={`p-3 rounded-lg border ${reflection.has_requirement_gaps ? "bg-amber-950/20 border-amber-900/60" : "bg-zinc-950 border-zinc-800"}`}>
                        <span className="text-[10px] text-zinc-400 uppercase font-medium block">Requirement Gaps</span>
                        <span className={`text-base font-bold font-mono ${reflection.has_requirement_gaps ? "text-amber-400" : "text-emerald-400"}`}>
                          {reflection.has_requirement_gaps ? "UNSATISFIED" : "SATISFIED"}
                        </span>
                      </div>

                      <div className={`p-3 rounded-lg border ${reflection.has_verification_gaps ? "bg-purple-950/20 border-purple-900/60" : "bg-zinc-950 border-zinc-800"}`}>
                        <span className="text-[10px] text-zinc-400 uppercase font-medium block">Verification Gaps</span>
                        <span className={`text-base font-bold font-mono ${reflection.has_verification_gaps ? "text-purple-400" : "text-emerald-400"}`}>
                          {reflection.has_verification_gaps ? "PENDING" : "VERIFIED"}
                        </span>
                      </div>

                      <div className={`p-3 rounded-lg border ${reflection.has_evidence_gaps ? "bg-blue-950/20 border-blue-900/60" : "bg-zinc-950 border-zinc-800"}`}>
                        <span className="text-[10px] text-zinc-400 uppercase font-medium block">Evidence Currency</span>
                        <span className={`text-base font-bold font-mono ${reflection.has_evidence_gaps ? "text-blue-400" : "text-emerald-400"}`}>
                          {reflection.has_evidence_gaps ? "STALE / UNCAL" : "CURRENT"}
                        </span>
                      </div>
                    </div>

                    {/* Summary Statement */}
                    {reflection.summary && (
                      <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-zinc-300 font-mono whitespace-pre-line leading-relaxed">
                        {reflection.summary}
                      </div>
                    )}

                    {/* Findings Filter & List */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                            Reasoning Findings ({reflection.findings.length})
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          {["ALL", "CRITICAL", "WARNING", "INFO"].map((filter) => (
                            <Button
                              key={filter}
                              size="sm"
                              variant={selectedFindingFilter === filter ? "secondary" : "ghost"}
                              onClick={() => setSelectedFindingFilter(filter)}
                              className="text-[11px] h-7 px-2.5"
                            >
                              {filter}
                            </Button>
                          ))}
                        </div>
                      </div>

                      {reflection.findings.length > 0 ? (
                        <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
                          {reflection.findings
                            .filter((f) => selectedFindingFilter === "ALL" || f.severity === selectedFindingFilter)
                            .map((finding) => (
                              <div
                                key={finding.id}
                                className={`p-3.5 rounded-lg border text-xs space-y-2 ${
                                  finding.severity === "CRITICAL"
                                    ? "bg-red-950/20 border-red-900/50"
                                    : finding.severity === "WARNING"
                                    ? "bg-amber-950/20 border-amber-900/40"
                                    : "bg-blue-950/20 border-blue-900/40"
                                }`}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <Badge
                                      variant="outline"
                                      className={`text-[10px] font-mono ${
                                        finding.severity === "CRITICAL"
                                          ? "text-red-400 border-red-800 bg-red-950/50"
                                          : finding.severity === "WARNING"
                                          ? "text-amber-400 border-amber-800 bg-amber-950/50"
                                          : "text-blue-400 border-blue-800 bg-blue-950/50"
                                      }`}
                                    >
                                      {finding.severity}
                                    </Badge>
                                    <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                                      {finding.finding_type}
                                    </Badge>
                                    {finding.affected_entity_id && (
                                      <Badge variant="outline" className="text-[10px] font-mono border-zinc-800 text-zinc-300">
                                        {finding.affected_entity_type}: {finding.affected_entity_id}
                                      </Badge>
                                    )}
                                  </div>
                                  {finding.follow_up_capability && (
                                    <span className="text-[10px] font-mono text-zinc-500">
                                      Remedy: {finding.follow_up_capability}
                                    </span>
                                  )}
                                </div>

                                <p className="font-medium text-zinc-100">{finding.title}</p>
                                <p className="text-zinc-300 text-xs leading-relaxed">{finding.description}</p>

                                {finding.recommended_remedy && (
                                  <div className="p-2 bg-zinc-950/70 border border-zinc-800/80 rounded text-[11px] text-zinc-300 flex items-start gap-1.5">
                                    <ArrowRight className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                                    <span>{finding.recommended_remedy}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-xs text-zinc-500 italic">
                          No reasoning findings or gaps identified. All evaluations conform to baselines.
                        </div>
                      )}
                    </div>

                    {/* Proposed Follow-Up Tasks & Bounded Replanning Panel */}
                    {reflection.additional_work_required && (
                      <div className="p-4 bg-indigo-950/20 border border-indigo-900/40 rounded-lg space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Repeat className="w-4 h-4 text-indigo-400" />
                            <span className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">
                              Bounded Follow-Up Plan Synthesis ({reflection.proposed_follow_up_tasks.length} Task(s))
                            </span>
                          </div>
                          <Badge variant="outline" className="text-[10px] font-mono border-indigo-800 text-indigo-400">
                            Bounded (Max 3 Cycles)
                          </Badge>
                        </div>

                        <div className="space-y-2">
                          {reflection.proposed_follow_up_tasks.map((task, idx) => (
                            <div key={idx} className="p-2.5 bg-zinc-950/80 border border-zinc-800 rounded text-xs flex items-center justify-between">
                              <div className="space-y-0.5">
                                <span className="font-mono text-[11px] text-indigo-300 font-medium block">
                                  Task {task.order_index || idx + 1}: {task.task_type}
                                </span>
                                <p className="text-zinc-400 text-[11px]">{task.description}</p>
                              </div>
                              <Badge variant="outline" className="text-[10px] font-mono border-zinc-800 text-zinc-400">
                                Read-Only
                              </Badge>
                            </div>
                          ))}
                        </div>

                        {replanSuccess && (
                          <div className="p-3 bg-emerald-950/30 border border-emerald-900/60 rounded text-xs text-emerald-300 flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                            <span>{replanSuccess}</span>
                          </div>
                        )}

                        <div className="flex items-center justify-between pt-1">
                          <span className="text-[11px] text-zinc-400">
                            {reflection.reflection_cycle >= 3
                              ? "Hard limit of 3 reflection cycles reached. Human engineering intervention required."
                              : `Automated replanning generates Cycle ${reflection.reflection_cycle + 1} task plan.`}
                          </span>
                          <Button
                            size="sm"
                            disabled={isReplanning || reflection.reflection_cycle >= 3}
                            onClick={handleReplanFromReflection}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs gap-1.5"
                          >
                            <Play className={`w-3.5 h-3.5 ${isReplanning ? "animate-spin" : ""}`} />
                            {isReplanning ? "Synthesizing Plan..." : `Synthesize Cycle ${reflection.reflection_cycle + 1} Plan`}
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Reflection Provenance & Integrity Digest */}
                    {reflection.provenance && (
                      <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-400 space-y-1.5">
                        <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] font-sans pb-1 border-b border-zinc-800/60">
                          <span className="font-semibold text-zinc-300">Reflection Provenance & Integrity Digest</span>
                          <span className="text-emerald-400">SHA-256 Verified</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Prompt / Rules:</span>
                          <span className="text-zinc-200">{reflection.provenance.prompt_id}:{reflection.provenance.prompt_version} (Rules {reflection.provenance.rule_set_version})</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Input Digest:</span>
                          <span className="text-zinc-300 font-mono text-[10px]">
                            {reflection.provenance.input_digest}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Output Digest:</span>
                          <span className="text-zinc-300 font-mono text-[10px]">
                            {reflection.provenance.output_digest}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-lg text-center space-y-2">
                    <p className="text-xs text-zinc-400">
                      Cognitive Reflection evaluates completed deterministic execution results against authoritative requirements, assumptions, and physical verification obligations.
                    </p>
                    <Button
                      size="sm"
                      onClick={() => handleTriggerReflection()}
                      disabled={isReflecting}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs gap-1.5"
                    >
                      <Scale className="w-3.5 h-3.5" />
                      {isReflecting ? "Evaluating..." : "Run Cognitive Reflection"}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* 7. Phase 2 Wave 3: Controlled Engineering Decision Preparation & Human Decision Gate */}
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 space-y-6">
              <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-950/60 border border-amber-800/80 rounded-lg text-amber-400">
                    <Gavel className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wide">
                        Engineering Decision Brief & Human Gate
                      </h3>
                      <Badge variant="outline" className="text-[10px] font-mono border-amber-800 text-amber-400 bg-amber-950/30">
                        Phase 2 Wave 3
                      </Badge>
                      {decisionBrief && (
                        <Badge
                          variant="outline"
                          className={`text-[10px] font-mono ${
                            decisionBrief.status === "DECIDED"
                              ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
                              : decisionBrief.status === "STALE"
                              ? "border-rose-800 text-rose-400 bg-rose-950/30"
                              : "border-sky-800 text-sky-400 bg-sky-950/30"
                          }`}
                        >
                          STATUS: {decisionBrief.status}
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Deterministic comparison of candidate alternatives without synthetic scoring. Final authority rests exclusively with the human engineer.
                    </p>
                  </div>
                </div>

                {!decisionBrief ? (
                  <Button
                    size="sm"
                    onClick={handlePrepareDecisionBrief}
                    disabled={isPreparingBrief}
                    className="bg-amber-600 hover:bg-amber-500 text-white text-xs gap-1.5 shadow-sm"
                  >
                    <Gavel className={`w-3.5 h-3.5 ${isPreparingBrief ? "animate-spin" : ""}`} />
                    {isPreparingBrief ? "Synthesizing Brief..." : "Synthesize Decision Brief"}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handlePrepareDecisionBrief}
                    disabled={isPreparingBrief}
                    className="text-xs border-zinc-700 text-zinc-300 hover:bg-zinc-800 gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isPreparingBrief ? "animate-spin" : ""}`} />
                    Re-Synthesize Brief
                  </Button>
                )}
              </div>

              {decisionError && (
                <div className="p-3.5 bg-rose-950/40 border border-rose-800/80 rounded-lg text-xs text-rose-200 flex items-start gap-2.5">
                  <AlertOctagon className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block mb-0.5">Decision Brief Notice</span>
                    <span>{decisionError}</span>
                  </div>
                </div>
              )}

              {decisionBrief ? (
                <div className="space-y-6">
                  {/* Brief Metadata Banner */}
                  <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                        Decision Question / Scope
                      </span>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                          Scope: {decisionBrief.scope}
                        </Badge>
                        <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 text-zinc-400">
                          Base Rev: {decisionBrief.base_revision}
                        </Badge>
                      </div>
                    </div>
                    <p className="text-xs text-zinc-200 font-medium leading-relaxed">
                      {decisionBrief.question}
                    </p>
                  </div>

                  {/* Stale Warning Banner if project revision advanced */}
                  {decisionBrief.base_revision !== systemRevision && (
                    <div className="p-3.5 bg-rose-950/30 border border-rose-800/60 rounded-lg flex items-center justify-between text-xs text-rose-300">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                        <span>
                          Baseline revision has advanced from Rev. {decisionBrief.base_revision} to Rev. {systemRevision}. This Decision Brief is marked STALE. Any decision attempt will be rejected.
                        </span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handlePrepareDecisionBrief}
                        className="text-xs border-rose-700 text-rose-200 hover:bg-rose-900/40 shrink-0"
                      >
                        Re-Synthesize for Rev. {systemRevision}
                      </Button>
                    </div>
                  )}

                  {/* Candidate Alternatives Cards */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Evaluated Candidate Alternatives ({decisionBrief.alternatives_data?.length || 0})
                      </span>
                      <span className="text-[11px] text-zinc-500 italic">
                        Strictly objective technical attributes — zero ranking or automated winner declaration
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {(decisionBrief.alternatives_data || []).map((alt) => (
                        <div
                          key={alt.id}
                          className={`p-4 bg-zinc-950 border rounded-lg space-y-3 ${
                            decisionBrief.selected_alternative_id === alt.id
                              ? "border-emerald-700/80 bg-emerald-950/10 ring-1 ring-emerald-600/30"
                              : "border-zinc-800 hover:border-zinc-700"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-xs text-zinc-100">{alt.name}</span>
                                {alt.topology && (
                                  <Badge variant="outline" className="text-[9px] font-mono border-zinc-700 text-zinc-400">
                                    {alt.topology}
                                  </Badge>
                                )}
                              </div>
                              <span className="font-mono text-[10px] text-zinc-500 block mt-0.5">ID: {alt.id}</span>
                            </div>
                            {decisionBrief.selected_alternative_id === alt.id && (
                              <Badge className="bg-emerald-600 text-white text-[10px] font-mono gap-1">
                                <Check className="w-3 h-3" /> RATIFIED
                              </Badge>
                            )}
                          </div>

                          {alt.description && (
                            <p className="text-[11px] text-zinc-400 leading-relaxed">{alt.description}</p>
                          )}

                          {/* Technical parameters */}
                          {alt.parameters && Object.keys(alt.parameters).length > 0 && (
                            <div className="p-2.5 bg-zinc-900/60 rounded border border-zinc-800/80 space-y-1">
                              <span className="text-[10px] uppercase font-mono text-zinc-500 block">Engineering Parameters</span>
                              <div className="flex flex-wrap gap-1.5 pt-0.5">
                                {Object.entries(alt.parameters).map(([k, v]) => (
                                  <span key={k} className="text-[10px] font-mono bg-zinc-800/80 text-zinc-300 px-2 py-0.5 rounded border border-zinc-700/60">
                                    {k}: {String(v)}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Blast radius summary */}
                          <div className="grid grid-cols-3 gap-2 text-[10px] font-mono text-zinc-400 pt-1">
                            <div>
                              <span className="text-zinc-500 block">BOM Mod:</span>
                              <span className="text-zinc-200">{alt.affected_components?.length || 0} part(s)</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 block">Interfaces:</span>
                              <span className="text-zinc-200">{alt.affected_interfaces?.length || 0} modified</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 block">Unknowns:</span>
                              <span className={alt.unknowns && alt.unknowns.length > 0 ? "text-amber-400" : "text-emerald-400"}>
                                {alt.unknowns?.length || 0} unverified
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Factual Requirement Comparison Table (Zero Synthetic Scoring) */}
                  <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Scale className="w-4 h-4 text-sky-400" />
                        <span className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                          Categorical Requirement Satisfaction Matrix
                        </span>
                      </div>
                      <Badge variant="outline" className="text-[10px] font-mono text-emerald-400 border-emerald-800 bg-emerald-950/20">
                        Zero Synthetic Scoring
                      </Badge>
                    </div>

                    {decisionBrief.requirement_summary?.comparison_matrix &&
                    Array.isArray(decisionBrief.requirement_summary.comparison_matrix) ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="border-b border-zinc-800 text-[11px] text-zinc-400 font-mono">
                              <th className="py-2 px-3">Alternative</th>
                              <th className="py-2 px-3">Satisfied</th>
                              <th className="py-2 px-3">Not Satisfied</th>
                              <th className="py-2 px-3">Unknown / Unverified</th>
                              <th className="py-2 px-3">Evaluations</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-800/60 font-mono text-[11px]">
                            {decisionBrief.requirement_summary.comparison_matrix.map((row: any, idx: number) => (
                              <tr key={idx} className="hover:bg-zinc-900/40">
                                <td className="py-2.5 px-3 font-medium text-zinc-200">
                                  {row.name || row.alternative_id}
                                </td>
                                <td className="py-2.5 px-3">
                                  <Badge variant="outline" className="bg-emerald-950/40 border-emerald-800 text-emerald-400 text-[10px]">
                                    {row.categorical_counts?.requirements_satisfied || 0}
                                  </Badge>
                                </td>
                                <td className="py-2.5 px-3">
                                  <Badge variant="outline" className="bg-rose-950/40 border-rose-800 text-rose-400 text-[10px]">
                                    {row.categorical_counts?.requirements_not_satisfied || 0}
                                  </Badge>
                                </td>
                                <td className="py-2.5 px-3">
                                  <Badge variant="outline" className="bg-amber-950/40 border-amber-800 text-amber-400 text-[10px]">
                                    {row.categorical_counts?.requirements_unknown || 0}
                                  </Badge>
                                </td>
                                <td className="py-2.5 px-3">
                                  <div className="flex flex-wrap gap-1">
                                    {row.requirement_evaluations &&
                                      Object.entries(row.requirement_evaluations).map(([reqId, ev]: [string, any]) => (
                                        <Badge
                                          key={reqId}
                                          variant="outline"
                                          className={`text-[9px] font-mono ${
                                            ev.state === "SATISFIED"
                                              ? "border-emerald-800 text-emerald-400 bg-emerald-950/30"
                                              : ev.state === "NOT_SATISFIED"
                                              ? "border-rose-800 text-rose-400 bg-rose-950/30"
                                              : ev.state === "UNKNOWN"
                                              ? "border-amber-800 text-amber-400 bg-amber-950/30"
                                              : "border-zinc-700 text-zinc-400 bg-zinc-900"
                                          }`}
                                        >
                                          {reqId}: {ev.state}
                                        </Badge>
                                      ))}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-xs text-zinc-500 italic">No formal requirements matrix attached.</p>
                    )}
                  </div>

                  {/* Objective Trade-Offs (Explicit Pros and Cons) */}
                  {decisionBrief.tradeoff_summary?.tradeoffs_by_alternative && (
                    <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                          Explicit Engineering Trade-Off Dimensions
                        </span>
                        <span className="text-[11px] text-zinc-500 italic">
                          Trade-offs are exposed factually without automated weighting or resolution
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(decisionBrief.tradeoff_summary.tradeoffs_by_alternative).map(
                          ([altId, t]: [string, any]) => (
                            <div key={altId} className="p-3 bg-zinc-900/60 border border-zinc-800 rounded-lg space-y-2 text-xs">
                              <span className="font-mono text-zinc-300 font-semibold block text-[11px] border-b border-zinc-800 pb-1">
                                {altId}
                              </span>
                              <div className="space-y-1">
                                <span className="text-[10px] text-emerald-400 uppercase font-mono font-medium block">
                                  Advantages (+)
                                </span>
                                {(t.advantages || []).map((adv: string, i: number) => (
                                  <div key={i} className="text-[11px] text-zinc-300 flex items-start gap-1.5">
                                    <span className="text-emerald-400 shrink-0">•</span>
                                    <span>{adv}</span>
                                  </div>
                                ))}
                              </div>
                              <div className="space-y-1 pt-1 border-t border-zinc-800/60">
                                <span className="text-[10px] text-rose-400 uppercase font-mono font-medium block">
                                  Disadvantages / Burdens (-)
                                </span>
                                {(t.disadvantages || []).map((dis: string, i: number) => (
                                  <div key={i} className="text-[11px] text-zinc-300 flex items-start gap-1.5">
                                    <span className="text-rose-400 shrink-0">•</span>
                                    <span>{dis}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}

                  {/* Decision Questions Formulated for Human Engineer */}
                  {decisionBrief.decision_questions && decisionBrief.decision_questions.length > 0 && (
                    <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <HelpCircle className="w-4 h-4 text-amber-400" />
                          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                            Engineering Decision Questions Requiring Judgment
                          </span>
                        </div>
                        <Badge variant="outline" className="text-[10px] font-mono border-amber-800 text-amber-400">
                          {decisionBrief.decision_questions.length} Question(s)
                        </Badge>
                      </div>

                      <div className="space-y-2">
                        {decisionBrief.decision_questions.map((q, idx) => (
                          <div
                            key={q.id || idx}
                            className="p-3 bg-zinc-900/60 border border-zinc-800/80 rounded-lg flex items-start justify-between gap-4"
                          >
                            <div className="space-y-1">
                              <p className="text-xs text-zinc-200 font-medium">{q.question}</p>
                              {q.context && <p className="text-[11px] text-zinc-400">{q.context}</p>}
                            </div>
                            <div className="flex flex-col items-end gap-1 shrink-0">
                              <Badge variant="outline" className="text-[9px] font-mono border-zinc-700 text-zinc-400">
                                {q.origin}
                              </Badge>
                              <Badge variant="outline" className="text-[9px] font-mono border-amber-800 text-amber-400 bg-amber-950/20">
                                HUMAN_REQUIRED
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* HUMAN DECISION AUTHORITY GATE */}
                  <div className="p-5 bg-gradient-to-b from-amber-950/20 to-zinc-950 border-2 border-amber-800/60 rounded-xl space-y-5">
                    <div className="flex items-center justify-between border-b border-amber-900/40 pb-3">
                      <div className="flex items-center gap-2.5">
                        <Lock className="w-4 h-4 text-amber-400" />
                        <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                          Human Engineering Decision Authority Gate
                        </h4>
                      </div>
                      <Badge className="bg-amber-950 text-amber-400 border border-amber-800 text-[10px] font-mono">
                        HUMAN AUTHORITY REQUIRED
                      </Badge>
                    </div>

                    <div className="p-3 bg-zinc-950/80 border border-amber-900/30 rounded text-[11px] text-zinc-300 leading-relaxed space-y-1">
                      <span className="font-semibold text-amber-400 block">Strict Governance Notice:</span>
                      <p>
                        AI models are strictly prohibited from selecting, approving, or ratifying engineering decisions. Every ratified decision creates a persistent, immutable <code className="text-amber-300">EngineeringDecisionRecord</code> bound to the current system revision and attributed to the authentic human engineer.
                      </p>
                    </div>

                    {decisionBrief.status === "DECIDED" && decisionResult ? (
                      <div className="p-4 bg-emerald-950/30 border border-emerald-800/60 rounded-lg space-y-2">
                        <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Engineering Decision Ratified & Recorded</span>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] font-mono text-zinc-300 pt-1">
                          <div>
                            <span className="text-zinc-500 block text-[10px]">Record ID:</span>
                            <span className="text-zinc-200 truncate block">{decisionResult.id?.substring(0, 12)}...</span>
                          </div>
                          <div>
                            <span className="text-zinc-500 block text-[10px]">Status:</span>
                            <span className="text-emerald-400 font-bold">{decisionResult.status}</span>
                          </div>
                          <div>
                            <span className="text-zinc-500 block text-[10px]">Decided By:</span>
                            <span className="text-zinc-200">{decisionResult.decided_by}</span>
                          </div>
                          <div>
                            <span className="text-zinc-500 block text-[10px]">Selected Alternative:</span>
                            <span className="text-emerald-300 font-bold">{decisionResult.selected_alternative_id || "N/A"}</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="text-[11px] font-semibold text-zinc-300 uppercase tracking-wider block">
                              Decision Action Type
                            </label>
                            <select
                              value={decisionType}
                              onChange={(e) => setDecisionType(e.target.value as HumanDecisionType)}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-600 font-mono"
                            >
                              <option value="ACCEPT_ALTERNATIVE">ACCEPT_ALTERNATIVE — Ratify candidate architecture</option>
                              <option value="REJECT_ALTERNATIVES">REJECT_ALTERNATIVES — Reject all evaluated options</option>
                              <option value="REQUEST_MORE_ANALYSIS">REQUEST_MORE_ANALYSIS — Commission follow-up analysis</option>
                              <option value="REQUEST_MORE_EVIDENCE">REQUEST_MORE_EVIDENCE — Require physical test measurements</option>
                              <option value="DEFER_DECISION">DEFER_DECISION — Defer pending system architecture review</option>
                              <option value="CHANGE_REQUIREMENT">CHANGE_REQUIREMENT — Escalate requirement modification</option>
                              <option value="CHANGE_CONSTRAINT">CHANGE_CONSTRAINT — Escalate constraint relaxation</option>
                            </select>
                          </div>

                          {(decisionType === "ACCEPT_ALTERNATIVE" || decisionType === "ADOPT_ALTERNATIVE") && (
                            <div className="space-y-1.5">
                              <label className="text-[11px] font-semibold text-zinc-300 uppercase tracking-wider block">
                                Select Alternative to Ratify
                              </label>
                              <select
                                value={selectedAlternativeId}
                                onChange={(e) => setSelectedAlternativeId(e.target.value)}
                                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-600 font-mono"
                              >
                                {(decisionBrief.alternatives_data || []).map((alt) => (
                                  <option key={alt.id} value={alt.id}>
                                    {alt.name} ({alt.id})
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[11px] font-semibold text-zinc-300 uppercase tracking-wider block">
                            Deciding Human Engineer (Identity)
                          </label>
                          <input
                            type="text"
                            value={decisionActor}
                            onChange={(e) => setDecisionActor(e.target.value)}
                            placeholder="e.g. Lead Systems Engineer (Jane Doe)"
                            className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-600"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[11px] font-semibold text-zinc-300 uppercase tracking-wider block">
                            Engineering Rationale & Justification
                          </label>
                          <textarea
                            value={decisionRationale}
                            onChange={(e) => setDecisionRationale(e.target.value)}
                            rows={3}
                            placeholder="Provide explicit engineering justification, trade-off rationale, and risk mitigations for the audit trail..."
                            className="w-full bg-zinc-950 border border-zinc-800 rounded p-2.5 text-xs text-zinc-200 focus:outline-none focus:border-amber-600 resize-none font-mono"
                          />
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          <span className="text-[11px] text-zinc-400">
                            Submitting records an immutable decision event in the Phase 1 governance audit log.
                          </span>
                          <Button
                            size="sm"
                            disabled={isRecordingDecision || decisionBrief.status === "STALE"}
                            onClick={handleRecordHumanDecision}
                            className="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold gap-1.5 px-4"
                          >
                            <Gavel className={`w-3.5 h-3.5 ${isRecordingDecision ? "animate-spin" : ""}`} />
                            {isRecordingDecision ? "Recording Decision..." : "Record Human Decision"}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Decision Brief Provenance & Integrity Digest */}
                  {decisionBrief.provenance && (
                    <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-400 space-y-1.5">
                      <div className="flex items-center justify-between text-zinc-500 uppercase text-[10px] font-sans pb-1 border-b border-zinc-800/60">
                        <span className="font-semibold text-zinc-300">Decision Brief Provenance & Integrity Digest</span>
                        <span className="text-emerald-400">SHA-256 Verified</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Prompt / Engine:</span>
                        <span className="text-zinc-200">
                          {decisionBrief.provenance.prompt_id}:{decisionBrief.provenance.prompt_version} (Rules {decisionBrief.provenance.rule_set_version})
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Input Digest:</span>
                        <span className="text-zinc-300 font-mono text-[10px]">
                          {decisionBrief.provenance.input_digest}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Output Digest:</span>
                        <span className="text-zinc-300 font-mono text-[10px]">
                          {decisionBrief.provenance.output_digest}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-lg text-center space-y-2">
                  <p className="text-xs text-zinc-400">
                    Prepare a structured Decision Brief comparing candidate alternatives against authoritative requirements, constraints, and reflection findings. Zero artificial scoring — ready for human review.
                  </p>
                  <Button
                    size="sm"
                    onClick={handlePrepareDecisionBrief}
                    disabled={isPreparingBrief}
                    className="bg-amber-600 hover:bg-amber-500 text-white text-xs gap-1.5"
                  >
                    <Gavel className="w-3.5 h-3.5" />
                    {isPreparingBrief ? "Synthesizing..." : "Prepare Engineering Decision Brief"}
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Phase 2 Wave 4: Engineering Memory, Decision History & Contextual Learning */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-6 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-4">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-teal-500/10 border border-teal-500/20 text-teal-400">
                <History className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  Engineering Memory & Contextual Learning
                  <Badge variant="outline" className="text-[10px] bg-teal-950/40 text-teal-300 border-teal-800/40">
                    ADVISORY CONTEXT
                  </Badge>
                </h3>
                <p className="text-xs text-zinc-400">
                  Surface historical engineering decisions, findings, and verification outcomes without treating history as authoritative fact.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <select
                aria-label="Filter by engineering domain"
                value={memoryDomainFilter}
                onChange={(e) => setMemoryDomainFilter(e.target.value)}
                className="bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded-md px-2.5 py-1.5 focus:outline-none focus:border-teal-500"
              >
                <option value="all">All Domains</option>
                <option value="power">Power</option>
                <option value="thermal">Thermal</option>
                <option value="rf">RF</option>
                <option value="analog">Analog</option>
                <option value="digital">Digital</option>
                <option value="general">General</option>
              </select>
              <Button
                size="sm"
                onClick={handleRetrieveMemories}
                disabled={isLoadingMemories}
                className="bg-teal-600 hover:bg-teal-500 text-white text-xs gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingMemories ? "animate-spin" : ""}`} />
                {isLoadingMemories ? "Searching..." : "Retrieve Memory"}
              </Button>
            </div>
          </div>

          {/* Epistemic Invariants Strip */}
          <div className="flex flex-wrap items-center gap-2 text-[10px] bg-zinc-950/70 p-2.5 rounded-lg border border-zinc-800">
            <span className="text-zinc-500 font-medium">Memory Governance:</span>
            <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-300 font-mono">
              HISTORICAL MEMORY ≠ CURRENT TRUTH
            </span>
            <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-300 font-mono">
              CURRENT SOURCE &gt; HISTORICAL MEMORY
            </span>
            <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-300 font-mono">
              HISTORICAL VERIFICATION ≠ CURRENT VERIFICATION
            </span>
            <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-700 text-zinc-300 font-mono">
              ZERO SYNTHETIC SCORING
            </span>
          </div>

          {/* Prominent Advisory Disclaimer */}
          <div className="p-3 bg-amber-950/20 border border-amber-900/40 rounded-lg flex items-start gap-2.5">
            <AlertOctagon className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <p className="text-xs font-semibold text-amber-200">
                Historical Context — Not Current Engineering Verification
              </p>
              <p className="text-[11px] text-amber-300/80">
                Historical engineering experience informs human judgment, but never overrides current datasheets, requirements, deterministic analyses, or physical verification.
              </p>
            </div>
          </div>

          {memoryError && (
            <div className="p-3 bg-rose-950/30 border border-rose-900/50 rounded-lg text-xs text-rose-300">
              {memoryError}
            </div>
          )}

          {/* Surfaced Memories List */}
          {surfacedMemories.length > 0 ? (
            <div className="space-y-3">
              {surfacedMemories.map((item, idx) => {
                const applicabilityColor =
                  item.applicability === "APPLICABLE"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : item.applicability === "POTENTIALLY_APPLICABLE"
                    ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                    : item.applicability === "NOT_APPLICABLE"
                    ? "bg-zinc-800 text-zinc-400 border-zinc-700"
                    : "bg-purple-500/10 text-purple-400 border-purple-500/30";

                return (
                  <div
                    key={item.memory.id || idx}
                    className="p-4 bg-zinc-950/80 border border-zinc-800 rounded-lg space-y-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] bg-zinc-900 text-zinc-300">
                          {item.memory.memory_type}
                        </Badge>
                        <Badge variant="outline" className={`text-[10px] font-semibold ${applicabilityColor}`}>
                          {item.applicability}
                        </Badge>
                        <Badge variant="outline" className="text-[10px] bg-zinc-900/60 text-zinc-400">
                          Outcome: {item.historical_outcome}
                        </Badge>
                      </div>
                      <span className="text-[11px] font-mono text-zinc-500">
                        Source: {item.memory.source_entity_type} ({item.memory.source_entity_id.slice(0, 8)}...)
                      </span>
                    </div>

                    <p className="text-xs text-zinc-200 font-medium">{item.memory.summary}</p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-zinc-900/50 p-3 rounded border border-zinc-800/80">
                      <div>
                        <span className="text-zinc-500 font-medium block text-[11px]">Why Surfaced:</span>
                        <span className="text-zinc-300">{item.why_surfaced}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 font-medium block text-[11px]">Current Relevance:</span>
                        <span className="text-zinc-300">{item.current_relevance}</span>
                      </div>
                    </div>

                    {/* Conflict Banner if Detected */}
                    {item.is_conflicting && (
                      <div className="p-2.5 bg-rose-950/30 border border-rose-900/50 rounded text-xs space-y-1">
                        <div className="flex items-center gap-1.5 font-semibold text-rose-300">
                          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                          Conflict with Current Authoritative Source
                        </div>
                        <p className="text-[11px] text-rose-200">
                          CURRENT AUTHORITATIVE SOURCE &gt; HISTORICAL MEMORY: Current specification takes precedence over historical experience.
                        </p>
                        {item.conflict_details?.parameter && (
                          <div className="text-[10px] font-mono text-zinc-300 pt-1">
                            Param: {item.conflict_details.parameter} | Current: {item.conflict_details.current_authoritative_value} vs Historical: {item.conflict_details.historical_memory_value}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Warnings */}
                    {item.warnings && item.warnings.length > 0 && (
                      <div className="space-y-1 text-[11px] text-amber-400/90 bg-amber-950/10 p-2 rounded border border-amber-900/30">
                        {item.warnings.map((w, wIdx) => (
                          <div key={wIdx} className="flex items-center gap-1.5">
                            <Info className="w-3 h-3 text-amber-400 shrink-0" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Human Engineer Feedback */}
                    <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60 text-xs">
                      <span className="text-zinc-500 text-[11px]">Engineer Feedback:</span>
                      <div className="flex items-center gap-1.5">
                        {memoryFeedbackStatus[item.memory.id] ? (
                          <Badge variant="outline" className="text-[10px] bg-teal-950/40 text-teal-300 border-teal-800/40">
                            Recorded: {memoryFeedbackStatus[item.memory.id]}
                          </Badge>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleMemoryFeedback(item.memory.id, "USEFUL")}
                              className="h-6 text-[10px] px-2 text-zinc-400 hover:text-emerald-300 gap-1"
                            >
                              <ThumbsUp className="w-3 h-3" />
                              Useful
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleMemoryFeedback(item.memory.id, "NOT_APPLICABLE")}
                              className="h-6 text-[10px] px-2 text-zinc-400 hover:text-rose-300 gap-1"
                            >
                              <ThumbsDown className="w-3 h-3" />
                              Not Applicable
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleMemoryFeedback(item.memory.id, "OUTDATED")}
                              className="h-6 text-[10px] px-2 text-zinc-400 hover:text-amber-300"
                            >
                              Outdated
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-lg text-center space-y-2">
              <BookOpen className="w-6 h-6 text-zinc-600 mx-auto" />
              <p className="text-xs text-zinc-400">
                Search authoritative historical records, past design decisions, and verification findings for this project context.
              </p>
              <Button
                size="sm"
                onClick={handleRetrieveMemories}
                disabled={isLoadingMemories}
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs gap-1.5"
              >
                <Search className="w-3.5 h-3.5" />
                {isLoadingMemories ? "Retrieving..." : "Search Historical Memory"}
              </Button>
            </div>
          )}
        </div>

        {/* Phase 2 Wave 5: Engineering Context Synthesis & Cognitive State */}
        <div className="border border-zinc-800 rounded-xl bg-zinc-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-cyan-400" />
              <div>
                <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                  Engineering Context Synthesis & Cognitive State
                  <Badge variant="outline" className="text-[10px] border-cyan-800 text-cyan-400 bg-cyan-950/40">
                    Phase 2 Wave 5
                  </Badge>
                  {contextSynthesis && (
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        contextSynthesis.status === "CURRENT"
                          ? "border-emerald-700 text-emerald-400 bg-emerald-950/40"
                          : contextSynthesis.status === "STALE"
                          ? "border-amber-700 text-amber-400 bg-amber-950/40"
                          : "border-zinc-700 text-zinc-400 bg-zinc-950/40"
                      }`}
                    >
                      {contextSynthesis.status} (Rev {contextSynthesis.base_revision})
                    </Badge>
                  )}
                </h3>
                <p className="text-xs text-zinc-400">
                  Revision-bound unified representation across authoritative facts, deterministic analysis, requirements, verification, and cross-source contradictions.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeHistoricalMemoryInContext}
                  onChange={(e) => setIncludeHistoricalMemoryInContext(e.target.checked)}
                  className="rounded border-zinc-700 bg-zinc-800 text-cyan-500 focus:ring-0 w-3.5 h-3.5"
                />
                Include Historical Memory
              </label>
              <Button
                size="sm"
                onClick={handleSynthesizeContext}
                disabled={isSynthesizingContext}
                className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSynthesizingContext ? "animate-spin" : ""}`} />
                {isSynthesizingContext ? "Synthesizing..." : "Synthesize Context Snapshot"}
              </Button>
            </div>
          </div>

          {/* Epistemic Invariant Alert */}
          <div className="bg-zinc-950 border border-zinc-800/80 rounded-lg p-3 text-[11px] text-zinc-400 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-zinc-300 font-mono">
              <Shield className="w-3.5 h-3.5 text-cyan-400" />
              <span>AUTHORITATIVE FACT ≠ DETERMINISTIC RESULT ≠ HISTORICAL CONTEXT ≠ AI INTERPRETATION</span>
            </div>
            <div className="flex items-center gap-2 text-zinc-500 text-[10px]">
              <span>AI AUTHORITY: NONE</span>
              <span>•</span>
              <span>CALCULATED ≠ PHYSICALLY VERIFIED</span>
              <span>•</span>
              <span>ZERO SYNTHETIC SCORING</span>
            </div>
          </div>

          {contextError && (
            <div className="p-3 bg-red-950/40 border border-red-800/50 rounded-lg text-xs text-red-300 flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
              <span>{contextError}</span>
            </div>
          )}

          {contextSynthesis ? (
            <div className="space-y-4">
              {/* Snapshot Metadata Strip */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Canonical SHA-256 Digest</div>
                  <div className="font-mono text-xs text-cyan-400 truncate" title={contextSynthesis.canonical_digest}>
                    {contextSynthesis.canonical_digest.slice(0, 16)}...
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Authoritative Facts</div>
                  <div className="text-xs text-zinc-200 font-semibold">
                    {contextSynthesis.authoritative_facts?.length || 0} Characterized Specifications
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Requirements & Verification</div>
                  <div className="text-xs text-zinc-200 font-semibold">
                    {contextSynthesis.requirements?.length || 0} Requirements / {contextSynthesis.verification_state?.requirements?.length || 0} Tests
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                  <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">Cross-Source Contradictions</div>
                  <div className="text-xs font-semibold">
                    {contextSynthesis.conflicts?.length > 0 ? (
                      <span className="text-red-400 flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        {contextSynthesis.conflicts.length} Conflicts Detected
                      </span>
                    ) : (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        0 Contradictions
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Category Sub-tabs */}
              <div className="flex border-b border-zinc-800 text-xs gap-4 pb-2">
                {[
                  { id: "STATE", label: `Current State (${contextSynthesis.current_state?.components?.length || 0} Parts)` },
                  { id: "DETERMINISTIC", label: `Deterministic Results (${contextSynthesis.deterministic_results?.length || 0})` },
                  { id: "REQUIREMENTS", label: `Requirements & Verification (${contextSynthesis.requirements?.length || 0})` },
                  { id: "CONTRADICTIONS", label: `Conflicts (${contextSynthesis.conflicts?.length || 0})` },
                  { id: "HISTORY", label: `Decisions & Memory (${(contextSynthesis.decision_history?.length || 0) + (contextSynthesis.historical_memory?.length || 0)})` },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setContextTab(tab.id as any)}
                    className={`pb-1 text-xs font-medium transition-colors ${
                      contextTab === tab.id
                        ? "text-cyan-400 border-b-2 border-cyan-400"
                        : "text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab 1: Current State */}
              {contextTab === "STATE" && (
                <div className="space-y-3">
                  <div className="text-xs text-zinc-400">Components and characterized physical specifications in active design revision:</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {(contextSynthesis.current_state?.components || []).map((comp: any, idx: number) => (
                      <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-zinc-200">{comp.ref_des || comp.name}</span>
                          <Badge variant="outline" className="text-[10px] text-zinc-400 border-zinc-700">
                            {comp.component_type}
                          </Badge>
                        </div>
                        <div className="text-xs text-zinc-400">Value: <span className="text-zinc-200">{comp.value || "N/A"}</span></div>
                        {comp.properties && Object.keys(comp.properties).length > 0 && (
                          <div className="text-[11px] text-zinc-500 font-mono mt-1">
                            {Object.entries(comp.properties).map(([k, v]) => `${k}: ${v}`).join(" | ")}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  {contextSynthesis.unknowns?.length > 0 && (
                    <div className="mt-3 p-3 bg-zinc-950 border border-amber-900/40 rounded-lg space-y-1">
                      <div className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
                        <HelpCircle className="w-3.5 h-3.5" />
                        Unresolved Engineering Unknowns ({contextSynthesis.unknowns.length})
                      </div>
                      <div className="space-y-1 text-xs text-zinc-400">
                        {contextSynthesis.unknowns.map((u: any, idx: number) => (
                          <div key={idx} className="flex items-start gap-2">
                            <span className="text-amber-500">•</span>
                            <span>{u.description || u.property || JSON.stringify(u)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Deterministic Results */}
              {contextTab === "DETERMINISTIC" && (
                <div className="space-y-3">
                  <div className="text-xs text-zinc-400">Deterministic calculation snapshots from rule engines and physical formulas:</div>
                  <div className="space-y-2">
                    {(contextSynthesis.deterministic_results || []).map((resItem: any, idx: number) => (
                      <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-zinc-200">{resItem.analysis_type}</span>
                          <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-800">
                            {resItem.status} (Confidence: {resItem.confidence})
                          </Badge>
                        </div>
                        {resItem.calculations && resItem.calculations.length > 0 && (
                          <div className="space-y-1.5">
                            {resItem.calculations.map((calc: any, cIdx: number) => (
                              <div key={cIdx} className="p-2 bg-zinc-900 border border-zinc-800/80 rounded text-xs space-y-1">
                                <div className="flex items-center justify-between">
                                  <span className="font-medium text-zinc-300">{calc.name}</span>
                                  <span className="font-mono text-cyan-400">{calc.formula}</span>
                                </div>
                                {calc.result && (
                                  <div className="text-[11px] text-zinc-400 font-mono">
                                    Result: {typeof calc.result === "object" ? JSON.stringify(calc.result) : calc.result} {calc.unit || ""}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tab 3: Requirements & Verification */}
              {contextTab === "REQUIREMENTS" && (
                <div className="space-y-3">
                  <div className="text-xs text-zinc-400">Requirements evaluated across 5 discrete states and laboratory physical verification items:</div>
                  <div className="space-y-2">
                    {(contextSynthesis.requirements || []).map((req: any, idx: number) => (
                      <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg flex items-center justify-between">
                        <div className="space-y-1">
                          <div className="text-xs font-semibold text-zinc-200 flex items-center gap-2">
                            <span>{req.requirement_key}</span>
                            <span className="text-zinc-400 font-normal">({req.title})</span>
                          </div>
                          <div className="text-[11px] text-zinc-500 font-mono">
                            Target: {req.target_property || "Unspecified"} | Max: {req.max_value || "None"} | Min: {req.min_value || "None"}
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            req.state === "SATISFIED"
                              ? "border-emerald-700 text-emerald-400 bg-emerald-950/40"
                              : req.state === "NOT_SATISFIED"
                              ? "border-red-700 text-red-400 bg-red-950/40"
                              : req.state === "UNKNOWN"
                              ? "border-amber-700 text-amber-400 bg-amber-950/40"
                              : "border-zinc-700 text-zinc-400"
                          }`}
                        >
                          {req.state}
                        </Badge>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 pt-3 border-t border-zinc-800 space-y-2">
                    <div className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                      <FileCheck className="w-4 h-4 text-cyan-400" />
                      Verification Requirements (CALCULATED ≠ PHYSICALLY VERIFIED)
                    </div>
                    <div className="space-y-1.5">
                      {(contextSynthesis.verification_state?.requirements || []).map((vr: any, idx: number) => (
                        <div key={idx} className="p-2.5 bg-zinc-950 border border-zinc-800 rounded text-xs flex items-center justify-between">
                          <div className="space-y-0.5">
                            <span className="font-semibold text-zinc-200">{vr.title || vr.code}</span>
                            <div className="text-[11px] text-zinc-500">Method: {vr.verification_method || vr.method}</div>
                          </div>
                          <Badge
                            variant="outline"
                            className={`text-xs ${
                              vr.status === "VERIFIED"
                                ? "border-emerald-700 text-emerald-400 bg-emerald-950/40"
                                : "border-amber-700 text-amber-400 bg-amber-950/40"
                            }`}
                          >
                            {vr.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 4: Contradictions & Conflicts */}
              {contextTab === "CONTRADICTIONS" && (
                <div className="space-y-3">
                  <div className="text-xs text-zinc-400">Cross-source contradictions requiring human engineering authority:</div>
                  {contextSynthesis.conflicts?.length > 0 ? (
                    <div className="space-y-2">
                      {contextSynthesis.conflicts.map((c: any, idx: number) => (
                        <div key={idx} className="p-3 bg-red-950/20 border border-red-800/60 rounded-lg space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-red-300 flex items-center gap-1.5">
                              <AlertOctagon className="w-4 h-4 text-red-400" />
                              {c.category}
                            </span>
                            {c.requires_human_review && (
                              <Badge variant="outline" className="text-[10px] border-red-700 text-red-300 bg-red-950/50">
                                Requires Human Authority
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-zinc-300">{c.description}</p>
                          <div className="text-[11px] text-zinc-500 font-mono">
                            Source A: {c.source_a_type} ({c.source_a_id}) vs Source B: {c.source_b_type} ({c.source_b_id})
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-xs text-zinc-400 space-y-1">
                      <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto" />
                      <p className="text-zinc-300 font-semibold">No active contradictions found</p>
                      <p className="text-zinc-500">All authoritative specifications, deterministic calculations, and assumptions are mutually consistent.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 5: Decisions & Memory */}
              {contextTab === "HISTORY" && (
                <div className="space-y-3">
                  <div className="text-xs text-zinc-400">Formal human decisions and contextual historical memory:</div>
                  <div className="space-y-2">
                    {(contextSynthesis.decision_history || []).map((dec: any, idx: number) => (
                      <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-zinc-200">{dec.title}</span>
                          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                            {dec.decision_type}
                          </Badge>
                        </div>
                        <p className="text-xs text-zinc-400">{dec.rationale || "No rationale recorded."}</p>
                        <div className="text-[10px] text-zinc-500">Decided by: {dec.decided_by}</div>
                      </div>
                    ))}
                    {(contextSynthesis.historical_memory || []).map((mem: any, idx: number) => (
                      <div key={idx} className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
                            <BookOpen className="w-3.5 h-3.5 text-zinc-400" />
                            {mem.memory?.summary || mem.summary}
                          </span>
                          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                            Historical Memory (Advisory)
                          </Badge>
                        </div>
                        <div className="text-[11px] text-zinc-500 font-mono">
                          Precedence rule: CURRENT AUTHORITATIVE SOURCE &gt; HISTORICAL MEMORY
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Grounded AI Context Explanation */}
              <div className="mt-4 pt-4 border-t border-zinc-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs font-semibold text-zinc-200">Grounded Context Explanation</span>
                  </div>
                  <span className="text-[10px] text-zinc-500 font-mono">AI AUTHORITY = NONE</span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={contextExplainQuery}
                    onChange={(e) => setContextExplainQuery(e.target.value)}
                    placeholder="Ask about thermal margins, unverified requirements, or potential conflicts..."
                    className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-cyan-500"
                    onKeyDown={(e) => e.key === "Enter" && handleExplainContext()}
                  />
                  <Button
                    size="sm"
                    onClick={handleExplainContext}
                    disabled={isExplainingContext || !contextExplainQuery.trim()}
                    className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs gap-1.5"
                  >
                    {isExplainingContext ? "Explaining..." : "Explain"}
                  </Button>
                </div>

                {contextExplainError && (
                  <div className="p-2.5 bg-red-950/30 border border-red-800/40 rounded text-xs text-red-300">
                    {contextExplainError}
                  </div>
                )}

                {contextExplanation && (
                  <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-2 text-xs">
                    <div className="text-zinc-300 whitespace-pre-wrap leading-relaxed">
                      {contextExplanation.explanation}
                    </div>
                    <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between text-[10px] text-zinc-500">
                      <span>Model: {contextExplanation.model_id}</span>
                      <span>{contextExplanation.confidence_notice}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-lg text-center space-y-2">
              <Layers className="w-6 h-6 text-zinc-600 mx-auto" />
              <p className="text-xs text-zinc-400">
                Synthesize the single authoritative, revision-bound engineering context snapshot for this project.
              </p>
              <Button
                size="sm"
                onClick={handleSynthesizeContext}
                disabled={isSynthesizingContext}
                className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSynthesizingContext ? "animate-spin" : ""}`} />
                {isSynthesizingContext ? "Synthesizing..." : "Synthesize Context Snapshot"}
              </Button>
            </div>
          )}
        </div>

        {/* Phase 2 Wave 6: Cognitive Engineering Workflow Orchestration */}
        <div className="border border-zinc-800 rounded-xl bg-zinc-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <GitBranch className="w-5 h-5 text-indigo-400" />
              <div>
                <h3 className="font-medium text-sm text-zinc-100 flex items-center gap-2">
                  Engineering Workflow Orchestration
                  <Badge variant="outline" className="text-[10px] border-indigo-800 text-indigo-400 bg-indigo-950/40">
                    Phase 2 Wave 6
                  </Badge>
                  {workflow && (
                    <Badge
                      variant="outline"
                      className={`text-xs ${
                        workflow.status === "COMPLETED"
                          ? "border-emerald-700 text-emerald-400 bg-emerald-950/40"
                          : workflow.status === "AWAITING_HUMAN"
                          ? "border-blue-700 text-blue-400 bg-blue-950/40"
                          : workflow.status === "BLOCKED" || workflow.status === "FAILED"
                          ? "border-red-700 text-red-400 bg-red-950/40"
                          : workflow.status === "STALE"
                          ? "border-amber-700 text-amber-400 bg-amber-950/40"
                          : "border-indigo-700 text-indigo-400 bg-indigo-950/40"
                      }`}
                    >
                      {workflow.status}
                    </Badge>
                  )}
                </h3>
                <p className="text-xs text-zinc-400">
                  Coordinated engineering lifecycle: Intent → Context → Task Plan → Execution → Reflection → Decision Prep → Unified Context.
                </p>
              </div>
            </div>
          </div>

          {/* Compact Workflow Timeline Strip */}
          {workflow && (
            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
                {/* Intent */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">1. Intent</span>
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs font-mono text-zinc-200">{workflow.intent_packet_id ? "RESOLVED" : "PENDING"}</span>
                  </div>
                </div>
                {/* Context */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">2. Context</span>
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs font-mono text-zinc-200">REV-{workflow.base_revision}</span>
                  </div>
                </div>
                {/* Plan */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">3. Task Plan</span>
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs font-mono text-zinc-200">{workflow.plan_id ? "VALIDATED" : "PENDING"}</span>
                  </div>
                </div>
                {/* Execution */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">4. Execution</span>
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs font-mono text-zinc-200">{workflow.execution_id ? "EXECUTED" : "PENDING"}</span>
                  </div>
                </div>
                {/* Reflection */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">5. Reflection</span>
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs font-mono text-zinc-200">CYCLE-{workflow.reflection_cycles || 1}</span>
                  </div>
                </div>
                {/* Decision Prep */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">6. Decision Prep</span>
                  <div className="flex items-center gap-1 mt-1">
                    {workflow.decision_brief_id ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-xs font-mono text-zinc-200">BRIEF READY</span>
                      </>
                    ) : (
                      <span className="text-xs font-mono text-zinc-500">—</span>
                    )}
                  </div>
                </div>
                {/* Unified Context */}
                <div className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800 flex flex-col justify-between">
                  <span className="text-[11px] text-zinc-400">7. Context</span>
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs font-mono text-zinc-200">{workflow.synthesized_context_id ? "SYNTHESIZED" : "PENDING"}</span>
                  </div>
                </div>
              </div>

              {/* Blocked / Awaiting Human Notice */}
              {workflow.blocking_reasons?.length > 0 && (
                <div className="p-3 bg-red-950/20 border border-red-800/60 rounded space-y-1 text-xs">
                  <div className="font-semibold text-red-300 flex items-center gap-1.5">
                    <AlertOctagon className="w-4 h-4 text-red-400" />
                    Workflow Blocked Reasons
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-zinc-300 font-mono text-[11px]">
                    {workflow.blocking_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Digest & Step details */}
              <div className="text-[11px] text-zinc-500 font-mono flex items-center justify-between">
                <span>Current Step: {workflow.current_step}</span>
                <span>Integrity Digest: {workflow.integrity_digest?.substring(0, 16)}...</span>
              </div>
            </div>
          )}

          {/* Launch Workflow Controls */}
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Start unified cognitive workflow (e.g., 'Verify LM7805 thermal margin and prepare decision brief')..."
              value={workflowPrompt}
              onChange={(e) => setWorkflowPrompt(e.target.value)}
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-600"
            />
            <Button
              size="sm"
              onClick={handleStartWorkflow}
              disabled={isStartingWorkflow}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs gap-1.5"
            >
              <Play className={`w-3.5 h-3.5 ${isStartingWorkflow ? "animate-spin" : ""}`} />
              {isStartingWorkflow ? "Orchestrating..." : "Start Unified Workflow"}
            </Button>
          </div>
          {workflowError && (
            <div className="p-2.5 bg-red-950/30 border border-red-800/40 rounded text-xs text-red-300">
              {workflowError}
            </div>
          )}
        </div>

        {/* Phase 2 Wave 7: Engineering Cognitive Interaction & Explainability */}
        <div className="border border-zinc-800 rounded-xl bg-zinc-900/60 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <HelpCircle className="w-5 h-5 text-teal-400" />
              <div>
                <h3 className="font-medium text-sm text-zinc-100 flex items-center gap-2">
                  Cognitive Interaction & Explainability
                  <Badge variant="outline" className="text-[10px] border-teal-800 text-teal-400 bg-teal-950/40">
                    Phase 2 Wave 7
                  </Badge>
                </h3>
                <p className="text-xs text-zinc-400">
                  Interrogate system state with grounded, revision-bound, evidence-aware explanations.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
              <span>CALCULATION ≠ PHYSICAL EVIDENCE</span>
              <span>•</span>
              <span>UNKNOWN ≠ SATISFIED</span>
            </div>
          </div>

          {/* Category Selector Buttons */}
          <div className="flex flex-wrap gap-1.5">
            {[
              { id: "WHY", label: "Why?" },
              { id: "WHAT_CHANGED", label: "What Changed?" },
              { id: "WHAT_IS_UNKNOWN", label: "What is Unknown?" },
              { id: "WHAT_SUPPORTS_THIS", label: "Evidence Chain" },
              { id: "WHAT_CONFLICTS", label: "Conflicts" },
              { id: "WHAT_REQUIREMENTS_ARE_AFFECTED", label: "Requirements" },
              { id: "WHAT_REQUIRES_VERIFICATION", label: "Verification" },
              { id: "WHAT_REQUIRES_HUMAN_DECISION", label: "Decision Brief" },
              { id: "WHY_IS_THIS_BLOCKED", label: "Why Blocked?" },
              { id: "WHY_IS_THIS_STALE", label: "Stale Check" },
            ].map((cat) => (
              <button
                key={cat.id}
                onClick={() => {
                  setExplainCategory(cat.id as ExplanationCategory);
                  handleInterrogate(cat.id as ExplanationCategory);
                }}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  explainCategory === cat.id
                    ? "bg-teal-600 text-white"
                    : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Targeted Interrogation Query Inputs */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
            <select
              value={explainTargetType}
              onChange={(e) => setExplainTargetType(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-teal-500"
            >
              <option value="Requirement">Requirement</option>
              <option value="Finding">Finding</option>
              <option value="Component">Component</option>
              <option value="DecisionBrief">Decision Brief</option>
              <option value="Workflow">Workflow</option>
            </select>
            <input
              type="text"
              placeholder="Target Entity ID (optional)..."
              value={explainTargetId}
              onChange={(e) => setExplainTargetId(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-teal-500"
            />
            <input
              type="text"
              placeholder="Specific question or query (optional)..."
              value={explainQuery}
              onChange={(e) => setExplainQuery(e.target.value)}
              className="md:col-span-2 bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-teal-500"
              onKeyDown={(e) => e.key === "Enter" && handleInterrogate()}
            />
          </div>

          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => handleInterrogate()}
              disabled={isInterrogating}
              className="bg-teal-600 hover:bg-teal-500 text-white text-xs gap-1.5"
            >
              <Search className={`w-3.5 h-3.5 ${isInterrogating ? "animate-spin" : ""}`} />
              {isInterrogating ? "Interrogating..." : "Interrogate System State"}
            </Button>
          </div>

          {interrogationError && (
            <div className="p-3 bg-red-950/30 border border-red-800/40 rounded text-xs text-red-300">
              {interrogationError}
            </div>
          )}

          {interrogationResponse && (
            <div className="space-y-4 pt-2 border-t border-zinc-800/80">
              {/* Epistemic Badges Header */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] bg-zinc-950 p-2.5 rounded border border-zinc-800">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                    Category: {interrogationResponse.category}
                  </Badge>
                  <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                    Authority: {interrogationResponse.authority}
                  </Badge>
                  <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                    Rev {interrogationResponse.base_revision}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-zinc-500 text-[10px] font-mono">
                  <span>AI AUTHORITY: NONE</span>
                  <span>•</span>
                  <span>ZERO SYNTHETIC SCORING</span>
                </div>
              </div>

              {/* Primary Statement */}
              <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
                {interrogationResponse.statement}
              </div>

              {/* Stale Warning if applicable */}
              {interrogationResponse.is_stale && (
                <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-lg text-xs space-y-1 text-amber-300">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    Stale Baseline Detected
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-zinc-300 text-[11px]">
                    {interrogationResponse.stale_factors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Evidence Chain */}
              {interrogationResponse.evidence_chain?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <Layers className="w-3.5 h-3.5 text-teal-400" />
                    Grounded Evidence Chain ({interrogationResponse.evidence_chain.length} Nodes)
                  </div>
                  <div className="space-y-1.5">
                    {interrogationResponse.evidence_chain.map((node, i) => (
                      <div
                        key={i}
                        className="p-2.5 bg-zinc-950 border border-zinc-800 rounded flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] text-zinc-500">[{node.step}]</span>
                            <span className="font-semibold text-zinc-200">{node.entity_type}</span>
                            <span className="text-[11px] font-mono text-zinc-400">({node.entity_id})</span>
                          </div>
                          <div className="text-[11px] text-zinc-300">{node.description}</div>
                        </div>
                        <div>
                          {node.is_physical ? (
                            <Badge className="bg-emerald-950/60 border border-emerald-800 text-emerald-400 text-[10px]">
                              Physical Lab Evidence
                            </Badge>
                          ) : node.is_calculation ? (
                            <Badge className="bg-cyan-950/60 border border-cyan-800 text-cyan-400 text-[10px]">
                              Deterministic Calculation
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px] text-zinc-500">
                              Structural Node
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Outstanding Human Actions */}
              {interrogationResponse.human_actions?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <CheckSquare className="w-3.5 h-3.5 text-amber-400" />
                    Outstanding Human Actions ({interrogationResponse.human_actions.length} Required)
                  </div>
                  <div className="space-y-1.5">
                    {interrogationResponse.human_actions.map((act, i) => (
                      <div
                        key={i}
                        className="p-2.5 bg-zinc-950 border border-zinc-800 rounded flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="font-semibold text-zinc-200 flex items-center gap-2">
                            <span>{act.title}</span>
                            <span className="text-[10px] font-mono text-zinc-500">({act.action_type})</span>
                          </div>
                          <div className="text-[11px] text-zinc-400">{act.description}</div>
                        </div>
                        <Badge
                          className={`text-[10px] ${
                            act.urgency === "HIGH"
                              ? "bg-red-950/60 border-red-800 text-red-400"
                              : "bg-amber-950/60 border-amber-800 text-amber-400"
                          }`}
                        >
                          {act.urgency}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Unresolved Unknowns */}
              {interrogationResponse.unknowns?.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-xs font-semibold text-zinc-300 flex items-center gap-2">
                    <SearchX className="w-3.5 h-3.5 text-red-400" />
                    Unresolved Unknowns ({interrogationResponse.unknowns.length})
                  </div>
                  <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded text-xs space-y-1">
                    <div className="text-[10px] text-zinc-500">
                      EPISTEMIC INVARIANT: UNKNOWN != SATISFIED. Missing parameters are never inferred.
                    </div>
                    <ul className="list-disc list-inside text-[11px] text-zinc-300 space-y-0.5">
                      {interrogationResponse.unknowns.map((u, i) => (
                        <li key={i}>{u}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Traceable References */}
              {interrogationResponse.traceable_references?.length > 0 && (
                <div className="pt-2 border-t border-zinc-800/80 flex flex-wrap items-center gap-1.5 text-[10px]">
                  <span className="text-zinc-500">Grounded References:</span>
                  {interrogationResponse.traceable_references.map((ref, i) => (
                    <span
                      key={i}
                      className="px-1.5 py-0.5 bg-zinc-950 border border-zinc-800 rounded font-mono text-zinc-400"
                    >
                      {ref.type}:{ref.id}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* PHASE 2 WAVE 8: ENGINEERING EVIDENCE & VERIFICATION WORKSPACE PANEL        */}
        {/* ========================================================================= */}
        <div className="p-5 bg-zinc-900/50 border border-zinc-800 rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-emerald-400" />
              <h3 className="text-sm font-semibold text-zinc-200">
                Engineering Evidence & Verification Workspace
              </h3>
              <Badge variant="outline" className="text-[10px] font-mono text-emerald-400 border-emerald-800">
                Phase 2 Wave 8
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono text-zinc-400">
                AI AUTHORITY: NONE | AUTONOMOUS CLOSURE: DISABLED
              </span>
            </div>
          </div>

          {/* Epistemic Invariants Strip */}
          <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold text-zinc-300">
              <Scale className="w-4 h-4 text-emerald-400" />
              <span>Epistemic Invariants & Human Closure Gate</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] font-mono text-zinc-400 pt-1">
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center">
                CALCULATED != PHYSICAL
              </div>
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center">
                UNKNOWN != SATISFIED
              </div>
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center">
                EXISTENCE != SUFFICIENCY
              </div>
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center text-emerald-400 border-emerald-900/60">
                HUMAN-GATED ONLY
              </div>
            </div>
          </div>

          {/* Workspace Loader Bar */}
          <div className="flex flex-col sm:flex-row items-center gap-2">
            <input
              type="text"
              value={customVerificationWorkflowId || workflow?.id || ""}
              onChange={(e) => setCustomVerificationWorkflowId(e.target.value)}
              placeholder="Enter Workflow ID (or run a cognitive workflow above)"
              className="flex-1 w-full px-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-xs text-zinc-200 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-emerald-600"
            />
            <Button
              onClick={() => handleLoadVerificationWorkspace()}
              disabled={isLoadingVerification || (!customVerificationWorkflowId && !workflow?.id)}
              className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-500 text-white text-xs flex items-center gap-2"
            >
              {isLoadingVerification ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Loading Workspace...
                </>
              ) : (
                <>
                  <CheckSquare className="w-3.5 h-3.5" />
                  Load Verification Obligations
                </>
              )}
            </Button>
          </div>

          {/* Error / Success Notifications */}
          {verificationError && (
            <div className="p-3 bg-red-950/40 border border-red-800 text-xs text-red-300 rounded flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
              <span>{verificationError}</span>
            </div>
          )}
          {evidenceSuccessMessage && (
            <div className="p-3 bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-300 rounded flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{evidenceSuccessMessage}</span>
            </div>
          )}
          {closeSuccessMessage && (
            <div className="p-3 bg-cyan-950/40 border border-cyan-800 text-xs text-cyan-300 rounded flex items-center gap-2">
              <BookmarkCheck className="w-4 h-4 text-cyan-400 shrink-0" />
              <span>{closeSuccessMessage}</span>
            </div>
          )}

          {/* Verification Workspace Content */}
          {verificationWorkspace && (
            <div className="space-y-4 pt-2">
              {/* Summary KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-zinc-500">Total Obligations</div>
                  <div className="text-lg font-bold text-zinc-100 font-mono">
                    {verificationWorkspace.summary.total_obligations}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-zinc-500">Verified</div>
                  <div className="text-lg font-bold text-emerald-400 font-mono">
                    {verificationWorkspace.summary.verified_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-zinc-500">Pending / Blocked</div>
                  <div className="text-lg font-bold text-amber-400 font-mono">
                    {verificationWorkspace.summary.pending_count} / {verificationWorkspace.summary.blocked_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-zinc-500">Missing Evidence</div>
                  <div className="text-lg font-bold text-red-400 font-mono">
                    {verificationWorkspace.summary.missing_evidence_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-zinc-500">Physical Tests Pending</div>
                  <div className="text-lg font-bold text-sky-400 font-mono">
                    {verificationWorkspace.summary.physical_tests_pending}
                  </div>
                </div>
              </div>

              {/* Provenance Integrity Digest */}
              <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <div className="flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Provenance Integrity Digest:</span>
                  <span className="text-zinc-200">{verificationWorkspace.provenance_integrity_digest}</span>
                </div>
                <div>Base Rev: {verificationWorkspace.base_revision}</div>
              </div>

              {/* Obligations Ledger & Detail Split */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Obligations List */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Obligations ({verificationWorkspace.obligations.length})</span>
                  </div>
                  <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                    {verificationWorkspace.obligations.map((obl) => {
                      const isSelected = obl.verification_requirement_id === selectedObligationId;
                      return (
                        <div
                          key={obl.verification_requirement_id}
                          onClick={() => handleSelectObligation(obl.verification_requirement_id)}
                          className={`p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                            isSelected
                              ? "bg-zinc-900 border-emerald-600 ring-1 ring-emerald-500/50"
                              : "bg-zinc-950 border-zinc-800 hover:border-zinc-700"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-zinc-200">{obl.code}</span>
                              <Badge
                                variant="outline"
                                className={`text-[10px] ${
                                  obl.status === "VERIFIED"
                                    ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                                    : obl.status === "FAILED"
                                    ? "text-red-400 border-red-800 bg-red-950/40"
                                    : obl.status === "WAIVED"
                                    ? "text-purple-400 border-purple-800 bg-purple-950/40"
                                    : "text-amber-400 border-amber-800 bg-amber-950/40"
                                }`}
                              >
                                {obl.status}
                              </Badge>
                            </div>
                            <Badge
                              className={`text-[10px] ${
                                obl.sufficiency === "SUFFICIENT"
                                  ? "bg-emerald-950/60 border-emerald-800 text-emerald-400"
                                  : obl.sufficiency === "INSUFFICIENT"
                                  ? "bg-amber-950/60 border-amber-800 text-amber-400"
                                  : obl.sufficiency === "MISSING"
                                  ? "bg-red-950/60 border-red-800 text-red-400"
                                  : "bg-zinc-800 text-zinc-400"
                              }`}
                            >
                              {obl.sufficiency}
                            </Badge>
                          </div>
                          <div className="text-zinc-300 font-medium line-clamp-1">{obl.title}</div>
                          <div className="mt-1 flex items-center gap-2 text-[10px] text-zinc-500">
                            <span>Method: {obl.method}</span>
                            <span>•</span>
                            <span>Cond: {obl.operating_condition}</span>
                            {obl.is_physical_required && (
                              <>
                                <span>•</span>
                                <span className="text-sky-400 font-semibold">Physical Req</span>
                              </>
                            )}
                          </div>
                          {obl.is_stale && (
                            <div className="mt-1 text-[10px] text-amber-400 flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3 text-amber-400" />
                              <span>Stale (superseded revision)</span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Selected Obligation Details & Actions */}
                <div className="space-y-3">
                  {obligationDetail ? (
                    <div className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3 text-xs">
                      <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                        <div>
                          <div className="font-mono text-[10px] text-zinc-500">
                            {obligationDetail.verification_requirement_id}
                          </div>
                          <div className="font-semibold text-zinc-100 text-sm">{obligationDetail.title}</div>
                        </div>
                        <Badge variant="outline" className="text-[10px] text-zinc-300">
                          {obligationDetail.status}
                        </Badge>
                      </div>

                      <div className="space-y-1 text-zinc-400 text-[11px]">
                        <div><strong className="text-zinc-300">Reason:</strong> {obligationDetail.reason}</div>
                        <div><strong className="text-zinc-300">Method:</strong> {obligationDetail.method}</div>
                        <div><strong className="text-zinc-300">Operating Condition:</strong> {obligationDetail.operating_condition}</div>
                        {obligationDetail.related_requirement_code && (
                          <div><strong className="text-zinc-300">Requirement:</strong> {obligationDetail.related_requirement_code}</div>
                        )}
                      </div>

                      {/* Attached Evidence Ledger */}
                      <div className="space-y-1.5 pt-2 border-t border-zinc-800">
                        <div className="font-semibold text-zinc-300 flex items-center justify-between text-[11px]">
                          <span>Attached Evidence ({obligationDetail.attached_evidence_items.length})</span>
                          <span className="text-zinc-500 font-mono text-[10px]">
                            {obligationDetail.has_physical_evidence ? "Physical: Present" : "Physical: Missing"}
                          </span>
                        </div>
                        {obligationDetail.attached_evidence_items.length === 0 ? (
                          <div className="p-2 bg-zinc-900 border border-zinc-800 rounded text-center text-zinc-500 text-[11px]">
                            No evidence attached yet. Register evidence below.
                          </div>
                        ) : (
                          <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                            {obligationDetail.attached_evidence_items.map((evi, i) => (
                              <div
                                key={i}
                                className="p-2 bg-zinc-900 border border-zinc-800 rounded text-[11px] space-y-1"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-zinc-200">{evi.evidence_type}</span>
                                  <Badge
                                    className={`text-[9px] ${
                                      evi.is_physical
                                        ? "bg-emerald-950 border-emerald-800 text-emerald-400"
                                        : "bg-cyan-950 border-cyan-800 text-cyan-400"
                                    }`}
                                  >
                                    {evi.is_physical ? "Physical Lab" : "Analytical"}
                                  </Badge>
                                </div>
                                <div className="text-zinc-300">{evi.description}</div>
                                {evi.value && (
                                  <div className="font-mono text-zinc-400 text-[10px]">
                                    Value: {evi.value} {evi.unit || ""}
                                  </div>
                                )}
                                <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono pt-0.5">
                                  <span>Src: {evi.source}</span>
                                  {evi.instrument && <span>Inst: {evi.instrument}</span>}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Attach Traceable Evidence Form */}
                      <div className="pt-2 border-t border-zinc-800 space-y-2">
                        <div className="font-semibold text-zinc-300 text-[11px] flex items-center gap-1.5">
                          <FileCheck className="w-3.5 h-3.5 text-sky-400" />
                          <span>Attach Traceable Evidence</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="text-[10px] text-zinc-500">Type</label>
                            <select
                              value={evidenceType}
                              onChange={(e) => {
                                setEvidenceType(e.target.value);
                                setIsPhysicalEvidence(
                                  ["MEASUREMENT", "LAB_OBSERVATION", "TEST_REPORT"].includes(e.target.value)
                                );
                              }}
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                            >
                              <option value="MEASUREMENT">MEASUREMENT (Physical)</option>
                              <option value="LAB_OBSERVATION">LAB_OBSERVATION (Physical)</option>
                              <option value="TEST_REPORT">TEST_REPORT (Physical)</option>
                              <option value="CALCULATION">CALCULATION (Analytical)</option>
                              <option value="SIMULATION_REPORT">SIMULATION_REPORT (Analytical)</option>
                              <option value="DATASHEET">DATASHEET (Authoritative Fact)</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-500">Source</label>
                            <input
                              type="text"
                              value={evidenceSource}
                              onChange={(e) => setEvidenceSource(e.target.value)}
                              placeholder="e.g. Lab Bench 4"
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="text-[10px] text-zinc-500">Measured Value</label>
                            <input
                              type="text"
                              value={evidenceValue}
                              onChange={(e) => setEvidenceValue(e.target.value)}
                              placeholder="e.g. 1.25"
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-500">Unit</label>
                            <input
                              type="text"
                              value={evidenceUnit}
                              onChange={(e) => setEvidenceUnit(e.target.value)}
                              placeholder="e.g. V, mA, °C"
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500">Description</label>
                          <input
                            type="text"
                            value={evidenceDesc}
                            onChange={(e) => setEvidenceDesc(e.target.value)}
                            placeholder="Bench test results under full load at 85°C..."
                            className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                          />
                        </div>
                        <div className="flex items-center justify-between text-xs pt-1">
                          <label className="flex items-center gap-1.5 text-zinc-400 text-[11px] cursor-pointer">
                            <input
                              type="checkbox"
                              checked={isPhysicalEvidence}
                              onChange={(e) => setIsPhysicalEvidence(e.target.checked)}
                              className="rounded border-zinc-700 bg-zinc-900"
                            />
                            <span>Physical Lab Measurement</span>
                          </label>
                          <Button
                            onClick={handleAttachEvidence}
                            disabled={isAttachingEvidence || !evidenceDesc.trim()}
                            className="bg-sky-600 hover:bg-sky-500 text-white text-xs h-7 px-3"
                          >
                            {isAttachingEvidence ? "Attaching..." : "Attach Evidence"}
                          </Button>
                        </div>
                      </div>

                      {/* Human Verification Closure Gate Form */}
                      <div className="pt-2 border-t border-zinc-800 space-y-2">
                        <div className="font-semibold text-emerald-400 text-[11px] flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <Gavel className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Human Verification Closure Gate</span>
                          </div>
                          <Badge variant="outline" className="text-[9px] text-amber-400 border-amber-800">
                            HUMAN ONLY
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="text-[10px] text-zinc-500">Decision</label>
                            <select
                              value={closeDecision}
                              onChange={(e) => setCloseDecision(e.target.value)}
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                            >
                              <option value="VERIFIED">VERIFIED (Pass)</option>
                              <option value="FAILED">FAILED (Non-compliant)</option>
                              <option value="WAIVED">WAIVED (Engineering Exemption)</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-500">Human Engineer Actor</label>
                            <input
                              type="text"
                              value={closeActor}
                              onChange={(e) => setCloseActor(e.target.value)}
                              placeholder="Engineer Name / Identity"
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-[10px] text-zinc-500">Closure Rationale (Mandatory)</label>
                          <textarea
                            value={closeRationale}
                            onChange={(e) => setCloseRationale(e.target.value)}
                            rows={2}
                            placeholder="Physical bench verification meets thermal threshold with 22% margin under full load."
                            className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs focus:outline-none focus:border-emerald-600"
                          />
                        </div>
                        {closeDecision === "WAIVED" && (
                          <div>
                            <label className="text-[10px] text-zinc-500">Waiver Justification</label>
                            <input
                              type="text"
                              value={closeWaiverReason}
                              onChange={(e) => setCloseWaiverReason(e.target.value)}
                              placeholder="Approved deviation per ECO-883..."
                              className="w-full px-2 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-zinc-200 text-xs"
                            />
                          </div>
                        )}
                        <Button
                          onClick={handleCloseVerification}
                          disabled={isClosingVerification || !closeRationale.trim()}
                          className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8"
                        >
                          {isClosingVerification ? "Executing Closure..." : "Ratify Verification Closure (Human Action)"}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-zinc-500 text-xs">
                      Select an obligation from the left ledger to inspect evidence and execute human closure.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* =========================================================================
            Phase 2 Wave 9: Cognitive Engineering Action & Closure Center Panel
            Invariant: ACTION CENTER != ENGINEERING SOURCE OF TRUTH (Aggregation only)
            Zero Synthetic Prioritization: NO priority_score, NO confidence_score
            No Autonomous Closure: AI cannot close actions, approve, or verify
           ========================================================================= */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-zinc-800 gap-2">
            <div>
              <div className="flex items-center gap-2">
                <CheckSquare className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-semibold text-zinc-100">
                  Engineering Action &amp; Closure Center
                </h3>
                <Badge variant="outline" className="text-[10px] font-mono text-indigo-400 border-indigo-800">
                  Phase 2 Wave 9
                </Badge>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Unified aggregation of outstanding engineering obligations across requirements, decisions, evidence, verification, and reviews.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-[10px] font-mono text-zinc-400 border-zinc-700">
                AGGREGATION ONLY
              </Badge>
              <Badge variant="outline" className="text-[10px] font-mono text-amber-400 border-amber-900">
                ZERO SYNTHETIC SCORES
              </Badge>
              <Badge variant="outline" className="text-[10px] font-mono text-emerald-400 border-emerald-900">
                AI AUTHORITY: NONE
              </Badge>
            </div>
          </div>

          {/* Core Architectural Invariants Strip */}
          <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg text-xs space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold text-zinc-300">
              <Scale className="w-4 h-4 text-indigo-400" />
              <span>Architectural Invariants &amp; Controlled Authority</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] font-mono text-zinc-400 pt-1">
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center">
                ACTION CENTER ≠ TRUTH OWNER
              </div>
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center">
                NO AUTONOMOUS CLOSURE
              </div>
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center">
                STATUS-GROUPED ONLY
              </div>
              <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded text-center text-indigo-400 border-indigo-900/60">
                WAVE 7/8 GROUNDED
              </div>
            </div>
          </div>

          {/* Category Filter Tabs & Refresh Controls */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {(["ALL", "BLOCKED", "DECISIONS", "EVIDENCE", "VERIFICATION", "REVIEWS", "UNKNOWN", "STALE"] as ActionCenterCategory[]).map((cat) => {
                const isSelected = selectedActionCategory === cat;
                const count = actionCenter?.summary
                  ? cat === "ALL"
                    ? actionCenter.summary.total_actions
                    : cat === "BLOCKED"
                    ? actionCenter.summary.blocked_count
                    : cat === "DECISIONS"
                    ? actionCenter.summary.decisions_count
                    : cat === "EVIDENCE"
                    ? actionCenter.summary.evidence_count
                    : cat === "VERIFICATION"
                    ? actionCenter.summary.verification_count
                    : cat === "REVIEWS"
                    ? actionCenter.summary.reviews_count
                    : cat === "UNKNOWN"
                    ? actionCenter.summary.unknowns_count
                    : actionCenter.summary.stale_count
                  : undefined;

                return (
                  <button
                    key={cat}
                    onClick={() => {
                      setSelectedActionCategory(cat);
                      handleLoadActionCenter(cat);
                    }}
                    className={`px-2.5 py-1 rounded text-xs font-medium font-mono transition-colors flex items-center gap-1.5 ${
                      isSelected
                        ? "bg-indigo-600 text-white"
                        : "bg-zinc-950 text-zinc-400 border border-zinc-800 hover:text-zinc-200 hover:border-zinc-700"
                    }`}
                  >
                    <span>{cat}</span>
                    {count !== undefined && (
                      <span className={`px-1 py-0.2 rounded text-[10px] ${
                        isSelected ? "bg-indigo-700 text-white" : "bg-zinc-800 text-zinc-400"
                      }`}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <Button
              onClick={() => handleLoadActionCenter()}
              disabled={isLoadingActions}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs flex items-center gap-1.5 shrink-0"
            >
              {isLoadingActions ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Aggregating...
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Refresh Action Center
                </>
              )}
            </Button>
          </div>

          {/* Error Banner */}
          {actionCenterError && (
            <div className="p-3 bg-red-950/40 border border-red-800 text-xs text-red-300 rounded flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
              <span>{actionCenterError}</span>
            </div>
          )}

          {/* Action Center Content */}
          {actionCenter && (
            <div className="space-y-4 pt-2">
              {/* Summary KPI Cards (Strictly Non-Synthetic) */}
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-2 text-xs">
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-zinc-500">Total</div>
                  <div className="text-base font-bold text-zinc-100 font-mono">
                    {actionCenter.summary.total_actions}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-rose-400">Blocked</div>
                  <div className="text-base font-bold text-rose-400 font-mono">
                    {actionCenter.summary.blocked_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-indigo-400">Decisions</div>
                  <div className="text-base font-bold text-indigo-400 font-mono">
                    {actionCenter.summary.decisions_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-amber-400">Evidence</div>
                  <div className="text-base font-bold text-amber-400 font-mono">
                    {actionCenter.summary.evidence_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-emerald-400">Verification</div>
                  <div className="text-base font-bold text-emerald-400 font-mono">
                    {actionCenter.summary.verification_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-purple-400">Reviews</div>
                  <div className="text-base font-bold text-purple-400 font-mono">
                    {actionCenter.summary.reviews_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-sky-400">Unknowns</div>
                  <div className="text-base font-bold text-sky-400 font-mono">
                    {actionCenter.summary.unknowns_count}
                  </div>
                </div>
                <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded">
                  <div className="text-[10px] text-orange-400">Stale</div>
                  <div className="text-base font-bold text-orange-400 font-mono">
                    {actionCenter.summary.stale_count}
                  </div>
                </div>
              </div>

              {/* Provenance & Integrity Digest Bar */}
              <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded flex flex-col sm:flex-row sm:items-center justify-between text-[11px] font-mono text-zinc-400 gap-2">
                <div className="flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Action Ledger Digest:</span>
                  <span className="text-zinc-200 truncate max-w-xs">{actionCenter.provenance_integrity_digest}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px]">
                  <span>Base Rev: {actionCenter.base_revision}</span>
                  <span>•</span>
                  <span>Isolation: Tenant Verified</span>
                </div>
              </div>

              {/* Ledger & Detail Split */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Actions Ledger */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-zinc-300 flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Action Items ({actionCenter.actions.length})</span>
                    </div>
                    <span className="text-[10px] font-mono text-zinc-500">
                      Category: {selectedActionCategory}
                    </span>
                  </div>

                  {actionCenter.actions.length === 0 ? (
                    <div className="p-8 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-zinc-500 text-xs">
                      No outstanding engineering actions for category {selectedActionCategory}.
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                      {actionCenter.actions.map((act) => {
                        const isSelected = act.action_id === selectedActionItem?.action_id;
                        return (
                          <div
                            key={act.action_id}
                            onClick={() => {
                              setSelectedActionItem(act);
                              setActionExplanation(null);
                            }}
                            className={`p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                              isSelected
                                ? "bg-zinc-900 border-indigo-600 ring-1 ring-indigo-500/50"
                                : "bg-zinc-950 border-zinc-800 hover:border-zinc-700"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className={`text-[9px] font-mono ${
                                    act.category === "BLOCKED"
                                      ? "text-rose-400 border-rose-800 bg-rose-950/40"
                                      : act.category === "DECISIONS"
                                      ? "text-indigo-400 border-indigo-800 bg-indigo-950/40"
                                      : act.category === "EVIDENCE"
                                      ? "text-amber-400 border-amber-800 bg-amber-950/40"
                                      : act.category === "VERIFICATION"
                                      ? "text-emerald-400 border-emerald-800 bg-emerald-950/40"
                                      : act.category === "REVIEWS"
                                      ? "text-purple-400 border-purple-800 bg-purple-950/40"
                                      : act.category === "UNKNOWN"
                                      ? "text-sky-400 border-sky-800 bg-sky-950/40"
                                      : "text-orange-400 border-orange-800 bg-orange-950/40"
                                  }`}
                                >
                                  {act.category}
                                </Badge>
                                <span className="text-[10px] font-mono text-zinc-500">
                                  {act.source_entity_type}
                                </span>
                              </div>
                              <Badge variant="outline" className="text-[9px] text-zinc-400">
                                {act.current_status}
                              </Badge>
                            </div>
                            <div className="text-zinc-200 font-medium line-clamp-1">{act.title}</div>
                            <div className="text-[11px] text-zinc-400 line-clamp-2 mt-1">
                              {act.required_human_action}
                            </div>
                            <div className="mt-2 flex items-center justify-between text-[10px] text-zinc-500 pt-1 border-t border-zinc-800/60 font-mono">
                              <span>Rev. {act.revision}</span>
                              <span className="truncate max-w-[180px]">{act.route_target}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Selected Action Details & Wave 7 Grounded Explanation */}
                <div className="space-y-3">
                  {selectedActionItem ? (
                    <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-3 text-xs">
                      <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                        <div>
                          <div className="font-mono text-[10px] text-zinc-500">
                            {selectedActionItem.source_entity_type} • {selectedActionItem.source_entity_id}
                          </div>
                          <div className="font-semibold text-zinc-100 text-sm mt-0.5">
                            {selectedActionItem.title}
                          </div>
                        </div>
                        <Badge
                          variant="outline"
                          className="text-[10px] font-mono text-indigo-400 border-indigo-800"
                        >
                          {selectedActionItem.category}
                        </Badge>
                      </div>

                      {/* Required Human Action Box */}
                      <div className="p-3 bg-indigo-950/20 border border-indigo-900/60 rounded text-indigo-200 space-y-1">
                        <div className="font-semibold text-[11px] flex items-center gap-1.5 text-indigo-300">
                          <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Required Human Engineering Action:</span>
                        </div>
                        <p className="text-[11px] leading-relaxed">
                          {selectedActionItem.required_human_action}
                        </p>
                      </div>

                      {/* Blockers & Dependencies */}
                      {selectedActionItem.blocking_reason && (
                        <div className="p-2.5 bg-rose-950/30 border border-rose-900/60 rounded text-rose-300 text-[11px] space-y-1">
                          <div className="font-semibold flex items-center gap-1.5 text-rose-400">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Blocking Reason:</span>
                          </div>
                          <p>{selectedActionItem.blocking_reason}</p>
                          {selectedActionItem.blocked_by.length > 0 && (
                            <div className="pt-1 text-[10px] font-mono text-rose-400">
                              Blocked By: {selectedActionItem.blocked_by.join(", ")}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Route Target & Details */}
                      <div className="space-y-1 text-zinc-400 text-[11px]">
                        <div><strong className="text-zinc-300">Description:</strong> {selectedActionItem.description}</div>
                        <div><strong className="text-zinc-300">Route Target:</strong> <code className="text-sky-400 font-mono text-[10px]">{selectedActionItem.route_target}</code></div>
                        {selectedActionItem.depends_on.length > 0 && (
                          <div><strong className="text-zinc-300">Depends On:</strong> <span className="font-mono text-[10px]">{selectedActionItem.depends_on.join(", ")}</span></div>
                        )}
                        {selectedActionItem.is_stale && selectedActionItem.stale_factors.length > 0 && (
                          <div className="text-amber-400"><strong className="text-amber-300">Stale Factors:</strong> {selectedActionItem.stale_factors.join("; ")}</div>
                        )}
                      </div>

                      {/* Actions Toolbar */}
                      <div className="pt-2 border-t border-zinc-800 flex items-center gap-2">
                        <Button
                          onClick={() => handleExplainActionItem(selectedActionItem)}
                          disabled={isExplainingAction}
                          className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs flex items-center gap-1.5"
                        >
                          {isExplainingAction ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              Generating Grounded Explanation...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-3.5 h-3.5" />
                              Explain Action (Wave 7 Grounded)
                            </>
                          )}
                        </Button>
                      </div>

                      {/* Wave 7 Grounded Explanation Container */}
                      {actionExplainError && (
                        <div className="p-2.5 bg-red-950/40 border border-red-800 text-xs text-red-300 rounded flex items-center gap-2">
                          <AlertOctagon className="w-3.5 h-3.5 text-red-400 shrink-0" />
                          <span>{actionExplainError}</span>
                        </div>
                      )}

                      {actionExplanation && (
                        <div className="mt-3 p-3 bg-zinc-900 border border-indigo-900/50 rounded-lg space-y-2 text-xs">
                          <div className="flex items-center justify-between pb-1.5 border-b border-zinc-800">
                            <span className="font-semibold text-indigo-300 flex items-center gap-1.5">
                              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                              Wave 7 Grounded Explanation
                            </span>
                            <Badge variant="outline" className="text-[9px] font-mono text-zinc-400 border-zinc-700">
                              INFORMATIONAL ONLY
                            </Badge>
                          </div>
                          <div className="text-zinc-200 text-[11px] leading-relaxed">
                            {actionExplanation.explanation}
                          </div>
                          {actionExplanation.statement && (
                            <div className="text-[11px] text-zinc-300">
                              <strong className="text-indigo-400">Statement:</strong> {actionExplanation.statement}
                            </div>
                          )}

                          {/* Grounded Evidence Chain Nodes */}
                          {actionExplanation.evidence_chain.length > 0 && (
                            <div className="space-y-1 pt-1">
                              <div className="font-semibold text-zinc-400 text-[10px] uppercase tracking-wide">
                                Supporting Evidence Chain ({actionExplanation.evidence_chain.length})
                              </div>
                              <div className="space-y-1">
                                {actionExplanation.evidence_chain.map((ev, i) => (
                                  <div key={i} className="p-1.5 bg-zinc-950 border border-zinc-800 rounded text-[10px] flex items-center justify-between">
                                    <span className="text-zinc-300">{ev.description}</span>
                                    <span className="font-mono text-zinc-500">{ev.entity_type}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Affected Requirements */}
                          {actionExplanation.requirement_refs.length > 0 && (
                            <div className="text-[10px] font-mono text-zinc-400 pt-1">
                              Affected Requirements: {actionExplanation.requirement_refs.join(", ")}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="p-8 bg-zinc-950 border border-zinc-800 rounded-lg text-center text-zinc-500 text-xs">
                      Select an action item from the ledger to inspect obligations, dependencies, and grounded explanation.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};


