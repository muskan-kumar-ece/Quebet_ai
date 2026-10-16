"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  FileText,
  Bookmark,
  HelpCircle,
  Scale,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertOctagon,
  ShieldCheck,
  ShieldAlert,
  Plus,
  RefreshCw,
  Loader2,
  Lock,
  Sparkles,
  UserCheck,
  FileCheck,
  Info,
  Layers,
  Clock,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { EngineeringSystem } from "./types";
import {
  EngineeringRequirement,
  EngineeringRequirementBaseline,
  EngineeringAssumption,
  EngineeringDecisionRecord,
  EngineeringDecisionAlternative,
  EngineeringTradeoff,
  EngineeringDecisionQuestion,
  EngineeringUnknownDisposition,
  EngineeringDesignReviewSession,
  EngineeringReviewCheckpoint,
  EngineeringReviewFinding,
  EngineeringReviewAction,
  ComparisonMatrixResponse,
  ReviewReadinessResponse,
  AIDecisionBriefResponse,
} from "./decision_types";

interface SystemDecisionCenterTabProps {
  system: EngineeringSystem;
  onSystemUpdated: () => void;
}

export const SystemDecisionCenterTab: React.FC<SystemDecisionCenterTabProps> = ({
  system,
  onSystemUpdated,
}) => {
  const [subTab, setSubTab] = useState<"requirements" | "assumptions" | "decisions" | "reviews">("requirements");
  const [loading, setLoading] = useState(false);

  // Requirements & Baselines State
  const [requirements, setRequirements] = useState<EngineeringRequirement[]>([]);
  const [baselines, setBaselines] = useState<EngineeringRequirementBaseline[]>([]);
  const [selectedReq, setSelectedReq] = useState<EngineeringRequirement | null>(null);
  const [coverageData, setCoverageData] = useState<any | null>(null);
  const [isCheckingCoverage, setIsCheckingCoverage] = useState(false);
  const [isCreatingReq, setIsCreatingReq] = useState(false);
  const [isCreatingBaseline, setIsCreatingBaseline] = useState(false);
  const [newReqKey, setNewReqKey] = useState("");
  const [newReqTitle, setNewReqTitle] = useState("");
  const [newReqStatement, setNewReqStatement] = useState("");
  const [newReqCategory, setNewReqCategory] = useState("FUNCTIONAL");
  const [newReqPriority, setNewReqPriority] = useState("SHALL");
  const [newBaselineName, setNewBaselineName] = useState("");

  // Assumptions State
  const [assumptions, setAssumptions] = useState<EngineeringAssumption[]>([]);
  const [isCreatingAssumption, setIsCreatingAssumption] = useState(false);
  const [newAssumpDesc, setNewAssumpDesc] = useState("");
  const [newAssumpBasis, setNewAssumpBasis] = useState("");
  const [newAssumpImpact, setNewAssumpImpact] = useState("REVIEW_REQUIRED");

  // Decisions & Alternatives State
  const [decisions, setDecisions] = useState<EngineeringDecisionRecord[]>([]);
  const [selectedDecision, setSelectedDecision] = useState<EngineeringDecisionRecord | null>(null);
  const [alternatives, setAlternatives] = useState<EngineeringDecisionAlternative[]>([]);
  const [tradeoffs, setTradeoffs] = useState<EngineeringTradeoff[]>([]);
  const [comparisonMatrix, setComparisonMatrix] = useState<ComparisonMatrixResponse | null>(null);
  const [aiBrief, setAiBrief] = useState<AIDecisionBriefResponse | null>(null);
  const [isLoadingBrief, setIsLoadingBrief] = useState(false);
  const [isCreatingDecision, setIsCreatingDecision] = useState(false);
  const [newDecTitle, setNewDecTitle] = useState("");
  const [newDecKey, setNewDecKey] = useState("");
  const [newDecType, setNewDecType] = useState("ARCHITECTURE_ALTERNATIVE");

  // Human Alternative Selection Modal State
  const [isSelectingAlt, setIsSelectingAlt] = useState(false);
  const [selectingAltId, setSelectingAltId] = useState<string>("");
  const [selectionRationale, setSelectionRationale] = useState("");
  const [selectionKeyReqs, setSelectionKeyReqs] = useState("");
  const [selectionTradeoffs, setSelectionTradeoffs] = useState("");
  const [selectionUnknowns, setSelectionUnknowns] = useState("");
  const [selectionVerification, setSelectionVerification] = useState("");

  // Design Reviews State
  const [reviews, setReviews] = useState<EngineeringDesignReviewSession[]>([]);
  const [selectedReview, setSelectedReview] = useState<EngineeringDesignReviewSession | null>(null);
  const [reviewReadiness, setReviewReadiness] = useState<ReviewReadinessResponse | null>(null);
  const [reviewQuestions, setReviewQuestions] = useState<EngineeringDecisionQuestion[]>([]);
  const [isCreatingReview, setIsCreatingReview] = useState(false);
  const [newReviewTitle, setNewReviewTitle] = useState("");
  const [waiveFindingId, setWaiveFindingId] = useState<string | null>(null);
  const [waiverRationale, setWaiverRationale] = useState("");
  const [answeringQuestionId, setAnsweringQuestionId] = useState<string | null>(null);
  const [questionAnswer, setQuestionAnswer] = useState("");
  const [reviewReport, setReviewReport] = useState<any | null>(null);

  // 1. Fetch requirements and baselines
  const loadRequirementsAndBaselines = useCallback(async () => {
    try {
      const [reqRes, baseRes] = await Promise.all([
        apiClient.get(`/systems/${system.id}/requirements`),
        apiClient.get(`/systems/${system.id}/requirement-baselines`),
      ]);
      setRequirements(reqRes.data?.data || []);
      setBaselines(baseRes.data?.data || []);
    } catch (err) {
      console.error("Failed to load requirements and baselines", err);
    }
  }, [system.id]);

  // 2. Fetch assumptions
  const loadAssumptions = useCallback(async () => {
    try {
      const res = await apiClient.get(`/systems/${system.id}/assumptions`);
      setAssumptions(res.data?.data || []);
    } catch (err) {
      console.error("Failed to load assumptions", err);
    }
  }, [system.id]);

  // 3. Fetch decisions
  const loadDecisions = useCallback(async () => {
    try {
      const res = await apiClient.get(`/systems/${system.id}/decisions`);
      const decList = res.data?.data || [];
      setDecisions(decList);
      if (decList.length > 0 && !selectedDecision) {
        setSelectedDecision(decList[0]);
      }
    } catch (err) {
      console.error("Failed to load decisions", err);
    }
  }, [system.id, selectedDecision]);

  // 4. Fetch decision details (alternatives, comparison matrix, tradeoffs)
  const loadDecisionDetails = useCallback(async (decisionId: string) => {
    try {
      const [altRes, compRes, troffRes] = await Promise.all([
        apiClient.get(`/decisions/${decisionId}/alternatives`),
        apiClient.get(`/decisions/${decisionId}/compare`),
        apiClient.get(`/decisions/${decisionId}/tradeoffs`),
      ]);
      setAlternatives(altRes.data?.data || []);
      setComparisonMatrix(compRes.data?.data || null);
      setTradeoffs(troffRes.data?.data || []);
    } catch (err) {
      console.error("Failed to load decision details", err);
    }
  }, []);

  // 5. Fetch reviews
  const loadReviews = useCallback(async () => {
    try {
      const res = await apiClient.get(`/systems/${system.id}/design-reviews`);
      const revList = res.data?.data || [];
      setReviews(revList);
      if (revList.length > 0 && !selectedReview) {
        setSelectedReview(revList[0]);
      }
    } catch (err) {
      console.error("Failed to load reviews", err);
    }
  }, [system.id, selectedReview]);

  // 6. Fetch review readiness & questions
  const loadReviewDetails = useCallback(async (reviewId: string) => {
    try {
      const [readRes, revObjRes] = await Promise.all([
        apiClient.get(`/design-reviews/${reviewId}/readiness`),
        apiClient.get(`/design-reviews/${reviewId}`),
      ]);
      setReviewReadiness(readRes.data?.data || null);
      setSelectedReview(revObjRes.data?.data || null);

      if (revObjRes.data?.data?.decision_id) {
        const qRes = await apiClient.get(`/decisions/${revObjRes.data.data.decision_id}/questions`);
        setReviewQuestions(qRes.data?.data || []);
      }
    } catch (err) {
      console.error("Failed to load review readiness", err);
    }
  }, []);

  useEffect(() => {
    loadRequirementsAndBaselines();
    loadAssumptions();
    loadDecisions();
    loadReviews();
  }, [loadRequirementsAndBaselines, loadAssumptions, loadDecisions, loadReviews]);

  useEffect(() => {
    if (selectedDecision) {
      loadDecisionDetails(selectedDecision.id);
    }
  }, [selectedDecision, loadDecisionDetails]);

  useEffect(() => {
    if (selectedReview) {
      loadReviewDetails(selectedReview.id);
    }
  }, [selectedReview?.id]);

  // Handle requirement creation
  const handleCreateRequirement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newReqKey || !newReqTitle || !newReqStatement) return;
    try {
      await apiClient.post(`/systems/${system.id}/requirements`, {
        requirement_key: newReqKey,
        title: newReqTitle,
        statement: newReqStatement,
        category: newReqCategory,
        priority: newReqPriority,
      });
      setNewReqKey("");
      setNewReqTitle("");
      setNewReqStatement("");
      setIsCreatingReq(false);
      loadRequirementsAndBaselines();
      onSystemUpdated();
    } catch (err) {
      console.error("Failed to create requirement", err);
    }
  };

  // Handle baseline creation
  const handleCreateBaseline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBaselineName) return;
    try {
      await apiClient.post(`/systems/${system.id}/requirement-baselines`, {
        name: newBaselineName,
      });
      setNewBaselineName("");
      setIsCreatingBaseline(false);
      loadRequirementsAndBaselines();
    } catch (err) {
      console.error("Failed to create baseline", err);
    }
  };

  // Handle deterministic coverage check
  const handleCheckCoverage = async () => {
    setIsCheckingCoverage(true);
    try {
      const res = await apiClient.get(`/systems/${system.id}/requirements/coverage`);
      setCoverageData(res.data?.data || null);
    } catch (err) {
      console.error("Failed to calculate requirement coverage", err);
    } finally {
      setIsCheckingCoverage(false);
    }
  };

  // Handle assumption creation
  const handleCreateAssumption = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAssumpDesc || !newAssumpBasis) return;
    try {
      await apiClient.post(`/systems/${system.id}/assumptions`, {
        description: newAssumpDesc,
        basis: newAssumpBasis,
        impact: newAssumpImpact,
      });
      setNewAssumpDesc("");
      setNewAssumpBasis("");
      setIsCreatingAssumption(false);
      loadAssumptions();
      onSystemUpdated();
    } catch (err) {
      console.error("Failed to create assumption", err);
    }
  };

  // Handle decision creation
  const handleCreateDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDecTitle || !newDecKey) return;
    try {
      const res = await apiClient.post(`/systems/${system.id}/decisions`, {
        title: newDecTitle,
        decision_key: newDecKey,
        decision_type: newDecType,
      });
      setNewDecTitle("");
      setNewDecKey("");
      setIsCreatingDecision(false);
      loadDecisions();
      if (res.data?.data) {
        setSelectedDecision(res.data.data);
      }
    } catch (err) {
      console.error("Failed to create decision", err);
    }
  };

  // Handle AI Decision Brief request
  const handleFetchAiBrief = async () => {
    if (!selectedDecision) return;
    setIsLoadingBrief(true);
    try {
      const res = await apiClient.get(`/decisions/${selectedDecision.id}/brief`);
      setAiBrief(res.data?.data || null);
    } catch (err) {
      console.error("Failed to load AI decision brief", err);
    } finally {
      setIsLoadingBrief(false);
    }
  };

  // Handle Human Alternative Selection
  const handleConfirmAlternativeSelection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDecision || !selectingAltId || !selectionRationale) return;
    try {
      const res = await apiClient.post(`/decisions/${selectedDecision.id}/select`, {
        alternative_id: selectingAltId,
        decision_rationale: selectionRationale,
        key_requirements: selectionKeyReqs ? selectionKeyReqs.split(",").map((s) => s.trim()) : [],
        key_tradeoffs: selectionTradeoffs ? selectionTradeoffs.split(",").map((s) => s.trim()) : [],
        accepted_unknowns: selectionUnknowns ? selectionUnknowns.split(",").map((s) => s.trim()) : [],
        verification_plan: selectionVerification,
      });
      setIsSelectingAlt(false);
      setSelectedDecision(res.data?.data || selectedDecision);
      loadDecisionDetails(selectedDecision.id);
      loadDecisions();
    } catch (err) {
      console.error("Failed to select alternative", err);
    }
  };

  // Handle Finding Waiver
  const handleWaiveFinding = async (findingId: string) => {
    if (!waiverRationale) return;
    try {
      await apiClient.post(`/design-reviews/findings/${findingId}/waive`, {
        waiver_rationale: waiverRationale,
      });
      setWaiveFindingId(null);
      setWaiverRationale("");
      if (selectedReview) {
        loadReviewDetails(selectedReview.id);
      }
    } catch (err) {
      console.error("Failed to waive finding", err);
    }
  };

  // Handle Answer Question
  const handleAnswerQuestion = async (questionId: string) => {
    if (!questionAnswer) return;
    try {
      await apiClient.post(`/decisions/questions/${questionId}/answer`, {
        answer: questionAnswer,
      });
      setAnsweringQuestionId(null);
      setQuestionAnswer("");
      if (selectedReview) {
        loadReviewDetails(selectedReview.id);
      }
    } catch (err) {
      console.error("Failed to answer question", err);
    }
  };

  // Handle Review Closure
  const handleCloseReview = async () => {
    if (!selectedReview) return;
    try {
      const res = await apiClient.post(`/design-reviews/${selectedReview.id}/close`);
      setSelectedReview(res.data?.data || null);
      loadReviews();
    } catch (err) {
      console.error("Failed to close review", err);
    }
  };

  // Handle View Review Report
  const handleViewReport = async () => {
    if (!selectedReview) return;
    try {
      const res = await apiClient.get(`/design-reviews/${selectedReview.id}/report`);
      setReviewReport(res.data?.data || null);
    } catch (err) {
      console.error("Failed to generate report", err);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-zinc-950 text-zinc-100 overflow-hidden select-none">
      {/* Wave 9 Sub-nav header */}
      <header className="h-12 border-b border-zinc-800 px-4 flex items-center justify-between bg-zinc-900/50 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Scale className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-semibold tracking-wide text-zinc-100">Engineering Decision Center</h2>
            <Badge variant="outline" className="text-[10px] py-0 h-4 border-emerald-800/80 bg-emerald-950/40 text-emerald-300">
              Rev {system.revision} Bound
            </Badge>
          </div>
          <div className="h-4 w-px bg-zinc-800" />
          <nav className="flex items-center gap-1">
            <button
              onClick={() => setSubTab("requirements")}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                subTab === "requirements"
                  ? "bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/60"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Requirements & Baselines ({requirements.length})
            </button>
            <button
              onClick={() => setSubTab("assumptions")}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                subTab === "assumptions"
                  ? "bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/60"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Assumptions ({assumptions.length})
            </button>
            <button
              onClick={() => setSubTab("decisions")}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                subTab === "decisions"
                  ? "bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/60"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Decision Records ({decisions.length})
            </button>
            <button
              onClick={() => setSubTab("reviews")}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                subTab === "reviews"
                  ? "bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/60"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Design Reviews ({reviews.length})
            </button>
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {subTab === "requirements" && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCheckCoverage}
                disabled={isCheckingCoverage}
                className="h-7 text-xs border-zinc-700 bg-zinc-800 text-zinc-200 hover:bg-zinc-700 flex items-center gap-1.5"
              >
                {isCheckingCoverage ? <Loader2 className="w-3 h-3 animate-spin" /> : <ShieldCheck className="w-3 h-3 text-emerald-400" />}
                Coverage Check
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsCreatingBaseline(true)}
                className="h-7 text-xs border-cyan-800/80 bg-cyan-950/30 text-cyan-300 hover:bg-cyan-900/50 flex items-center gap-1.5"
              >
                <Bookmark className="w-3 h-3" />
                Freeze Baseline
              </Button>
              <Button
                size="sm"
                onClick={() => setIsCreatingReq(true)}
                className="h-7 text-xs bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5"
              >
                <Plus className="w-3 h-3" />
                Add Requirement
              </Button>
            </>
          )}

          {subTab === "assumptions" && (
            <Button
              size="sm"
              onClick={() => setIsCreatingAssumption(true)}
              className="h-7 text-xs bg-purple-600 hover:bg-purple-500 text-white flex items-center gap-1.5"
            >
              <Plus className="w-3 h-3" />
              Add Assumption
            </Button>
          )}

          {subTab === "decisions" && (
            <Button
              size="sm"
              onClick={() => setIsCreatingDecision(true)}
              className="h-7 text-xs bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5"
            >
              <Plus className="w-3 h-3" />
              New Decision Record
            </Button>
          )}

          {subTab === "reviews" && (
            <Button
              size="sm"
              onClick={() => setIsCreatingReview(true)}
              className="h-7 text-xs bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-1.5"
            >
              <Plus className="w-3 h-3" />
              Schedule Design Review
            </Button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto p-4">
        {/* SUBTAB 1: REQUIREMENTS & BASELINES */}
        {subTab === "requirements" && (
          <div className="space-y-6 max-w-7xl mx-auto">
            {/* Deterministic Coverage Summary Banner */}
            {coverageData && (
              <div className="p-4 rounded-lg bg-zinc-900/80 border border-zinc-800 grid grid-cols-4 gap-4">
                <div className="flex flex-col">
                  <span className="text-[11px] text-zinc-400 font-medium">COVERED</span>
                  <span className="text-xl font-bold text-emerald-400">{coverageData.covered_count || 0}</span>
                  <span className="text-[10px] text-zinc-500">Formally mapped with verification</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] text-zinc-400 font-medium">PARTIALLY COVERED</span>
                  <span className="text-xl font-bold text-amber-400">{coverageData.partially_covered_count || 0}</span>
                  <span className="text-[10px] text-zinc-500">Partial verification requirement link</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] text-zinc-400 font-medium">NOT COVERED</span>
                  <span className="text-xl font-bold text-red-400">{coverageData.not_covered_count || 0}</span>
                  <span className="text-[10px] text-zinc-500">Missing verification obligation</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] text-zinc-400 font-medium">UNKNOWN</span>
                  <span className="text-xl font-bold text-zinc-400">{coverageData.unknown_count || 0}</span>
                  <span className="text-[10px] text-zinc-500">Epistemological boundary: not verified</span>
                </div>
              </div>
            )}

            {/* Frozen Baselines Section */}
            {baselines.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Bookmark className="w-3.5 h-3.5 text-cyan-400" />
                  Frozen Requirement Baselines ({baselines.length})
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {baselines.map((b) => (
                    <div key={b.id} className="p-3 rounded-md bg-zinc-900/60 border border-cyan-900/40 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-cyan-200">{b.name}</span>
                        <Badge variant="outline" className="text-[10px] border-cyan-800 text-cyan-300">
                          Rev {b.system_revision}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-zinc-400 font-mono truncate">
                        Hash: {b.baseline_hash.substring(0, 16)}...
                      </div>
                      <div className="text-[10px] text-zinc-500 flex items-center justify-between pt-1 border-t border-zinc-800/80">
                        <span>{b.requirement_ids.length} requirements frozen</span>
                        <span className="flex items-center gap-1 text-emerald-400">
                          <Lock className="w-3 h-3" /> Immutable
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Requirements Table */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                System Engineering Requirements ({requirements.length})
              </h3>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-zinc-900 text-zinc-400 border-b border-zinc-800 text-[11px]">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">Key</th>
                      <th className="py-2.5 px-3 font-semibold">Title</th>
                      <th className="py-2.5 px-3 font-semibold">Category</th>
                      <th className="py-2.5 px-3 font-semibold">Priority</th>
                      <th className="py-2.5 px-3 font-semibold">Structured Expression</th>
                      <th className="py-2.5 px-3 font-semibold">Verification</th>
                      <th className="py-2.5 px-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {requirements.map((req) => (
                      <tr
                        key={req.id}
                        onClick={() => setSelectedReq(req)}
                        className={`hover:bg-zinc-800/40 cursor-pointer transition-colors ${
                          selectedReq?.id === req.id ? "bg-zinc-800/60" : ""
                        }`}
                      >
                        <td className="py-2.5 px-3 font-mono font-bold text-emerald-400">{req.requirement_key}</td>
                        <td className="py-2.5 px-3 font-medium text-zinc-200">{req.title}</td>
                        <td className="py-2.5 px-3">
                          <Badge variant="outline" className="text-[10px] border-zinc-700 bg-zinc-800/50 text-zinc-300">
                            {req.category}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge
                            className={`text-[10px] ${
                              req.priority === "SHALL"
                                ? "bg-red-950/80 text-red-300 border-red-800"
                                : req.priority === "SHOULD"
                                ? "bg-amber-950/80 text-amber-300 border-amber-800"
                                : "bg-blue-950/80 text-blue-300 border-blue-800"
                            }`}
                          >
                            {req.priority}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-cyan-300">
                          {req.structured_expression ? (
                            <span>
                              {req.structured_expression.parameter} {req.structured_expression.operator}{" "}
                              {req.structured_expression.nominal_value ?? req.structured_expression.max_value}{" "}
                              {req.structured_expression.unit}
                            </span>
                          ) : (
                            <span className="text-zinc-600">Textual</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-zinc-400">{req.verification_method || "UNASSIGNED"}</td>
                        <td className="py-2.5 px-3">
                          <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                            {req.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                    {requirements.length === 0 && (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-zinc-500">
                          No engineering requirements defined for this system. Click &quot;Add Requirement&quot; to begin.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 2: ENGINEERING ASSUMPTIONS */}
        {subTab === "assumptions" && (
          <div className="space-y-4 max-w-6xl mx-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-purple-400" />
                Active Engineering Assumptions & Sensitivity ({assumptions.length})
              </h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {assumptions.map((assump) => (
                <div key={assump.id} className="p-4 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-2">
                  <div className="flex items-start justify-between">
                    <span className="text-xs font-bold text-zinc-200 leading-tight">{assump.description}</span>
                    <Badge
                      className={`text-[10px] ml-2 shrink-0 ${
                        assump.impact === "CRITICAL" || assump.impact === "INVALIDATES_ARCHITECTURE"
                          ? "bg-red-950 text-red-300 border-red-800"
                          : "bg-amber-950 text-amber-300 border-amber-800"
                      }`}
                    >
                      {assump.impact}
                    </Badge>
                  </div>
                  <div className="text-xs text-zinc-400">
                    <span className="text-zinc-500">Basis: </span> {assump.basis}
                  </div>
                  <div className="flex items-center justify-between text-[11px] pt-2 border-t border-zinc-800/80">
                    <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                      Status: {assump.status}
                    </Badge>
                    <span className="text-zinc-500 text-[10px]">System Rev {assump.system_revision}</span>
                  </div>
                </div>
              ))}
              {assumptions.length === 0 && (
                <div className="col-span-2 py-12 text-center text-zinc-500 border border-dashed border-zinc-800 rounded-lg">
                  No assumptions tracked. Formal engineering assumptions prevent silent invalidation.
                </div>
              )}
            </div>
          </div>
        )}

        {/* SUBTAB 3: DECISION RECORDS & MULTIDIMENSIONAL COMPARISON */}
        {subTab === "decisions" && (
          <div className="space-y-6 max-w-7xl mx-auto">
            {/* Decision Selector & Controls */}
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider">Active Decision:</span>
                <select
                  value={selectedDecision?.id || ""}
                  onChange={(e) => {
                    const dec = decisions.find((d) => d.id === e.target.value);
                    if (dec) setSelectedDecision(dec);
                  }}
                  className="bg-zinc-900 border border-zinc-700 text-xs rounded px-2.5 py-1 text-zinc-200"
                >
                  {decisions.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.decision_key}: {d.title} ({d.status})
                    </option>
                  ))}
                </select>
                {selectedDecision && (
                  <Badge variant="outline" className="text-[10px] border-emerald-800 text-emerald-300">
                    Status: {selectedDecision.status}
                  </Badge>
                )}
              </div>

              {selectedDecision && (
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleFetchAiBrief}
                    disabled={isLoadingBrief}
                    className="h-7 text-xs border-purple-800/80 bg-purple-950/30 text-purple-300 hover:bg-purple-900/50 flex items-center gap-1.5"
                  >
                    {isLoadingBrief ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    Generate AI Decision Brief
                  </Button>
                </div>
              )}
            </div>

            {/* AI Decision Brief Banner (STRICTLY INFORMATIONAL & LABELED) */}
            {aiBrief && (
              <div className="p-4 rounded-lg bg-purple-950/20 border border-purple-800/60 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span className="text-xs font-bold text-purple-200">AI Decision Brief</span>
                    <Badge className="text-[10px] bg-purple-900/80 text-purple-300 border-purple-700">
                      ORIGIN: AI_GENERATED (INFORMATIONAL ONLY)
                    </Badge>
                  </div>
                  <span className="text-[10px] text-zinc-400 font-mono">
                    Model: {aiBrief.provenance.model_identifier}
                  </span>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">{aiBrief.executive_summary}</p>
                <div className="text-[11px] text-amber-300/80 italic font-medium pt-1">
                  Notice: {aiBrief.disclaimer}
                </div>
              </div>
            )}

            {/* MULTIDIMENSIONAL COMPARISON MATRIX (ZERO SYNTHETIC SCORES) */}
            {comparisonMatrix && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Scale className="w-3.5 h-3.5 text-emerald-400" />
                    Multidimensional Engineering Comparison Matrix (Zero Synthetic Scoring)
                  </h3>
                  <span className="text-[11px] text-zinc-500">
                    Decision bound to System Revision {comparisonMatrix.system_revision}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {comparisonMatrix.comparison_matrix.map((alt) => {
                    const isSelected = selectedDecision?.selected_alternative_id === alt.alternative_id;
                    return (
                      <div
                        key={alt.alternative_id}
                        className={`p-4 rounded-lg bg-zinc-900/70 border space-y-3 flex flex-col justify-between ${
                          isSelected
                            ? "border-emerald-500 shadow-md shadow-emerald-950/50"
                            : "border-zinc-800 hover:border-zinc-700"
                        }`}
                      >
                        <div className="space-y-2">
                          <div className="flex items-start justify-between">
                            <span className="text-xs font-bold text-zinc-100">{alt.name}</span>
                            <Badge
                              className={`text-[10px] ${
                                isSelected
                                  ? "bg-emerald-950 text-emerald-300 border-emerald-700"
                                  : "bg-zinc-800 text-zinc-400 border-zinc-700"
                              }`}
                            >
                              {isSelected ? "SELECTED BY ENGINEER" : alt.status}
                            </Badge>
                          </div>

                          {/* Dimensions */}
                          <div className="space-y-1.5 text-xs text-zinc-300 pt-2 border-t border-zinc-800">
                            <div>
                              <span className="text-zinc-500 font-semibold block text-[10px] uppercase">
                                Engineering Effects:
                              </span>
                              <pre className="text-[11px] font-mono text-zinc-300 bg-zinc-950 p-1.5 rounded overflow-x-auto mt-0.5">
                                {JSON.stringify(alt.engineering_effects, null, 2)}
                              </pre>
                            </div>

                            <div>
                              <span className="text-zinc-500 font-semibold block text-[10px] uppercase">
                                Requirement Effects:
                              </span>
                              <pre className="text-[11px] font-mono text-emerald-300 bg-zinc-950 p-1.5 rounded overflow-x-auto mt-0.5">
                                {JSON.stringify(alt.requirement_effects, null, 2)}
                              </pre>
                            </div>

                            <div>
                              <span className="text-zinc-500 font-semibold block text-[10px] uppercase">
                                Unknowns ({alt.unknowns.length}):
                              </span>
                              {alt.unknowns.length > 0 ? (
                                <ul className="list-disc pl-4 text-[11px] text-amber-300/90 mt-0.5">
                                  {alt.unknowns.map((u, i) => (
                                    <li key={i}>{u}</li>
                                  ))}
                                </ul>
                              ) : (
                                <span className="text-[11px] text-zinc-600">None declared</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Engineer Selection Action */}
                        <div className="pt-3 border-t border-zinc-800">
                          {isSelected ? (
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
                              <CheckCircle2 className="w-4 h-4" /> Formally Selected Alternative
                            </div>
                          ) : (
                            <Button
                              size="sm"
                              onClick={() => {
                                setSelectingAltId(alt.alternative_id);
                                setIsSelectingAlt(true);
                              }}
                              className="w-full h-7 text-xs bg-zinc-800 hover:bg-emerald-600 text-zinc-200 hover:text-white flex items-center justify-center gap-1.5"
                            >
                              <UserCheck className="w-3.5 h-3.5" />
                              Select Alternative (Engineer Authority)
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Formal Human Decision Record if selected */}
            {selectedDecision?.status === "DECIDED" && selectedDecision.rationale && (
              <div className="p-4 rounded-lg bg-emerald-950/20 border border-emerald-800/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Formal Decision Record (Human Signed)
                  </span>
                  <span className="text-[11px] text-zinc-400">
                    Decided by: {selectedDecision.decided_by} at {selectedDecision.decided_at}
                  </span>
                </div>
                <div className="text-xs text-zinc-300">
                  <span className="text-zinc-500 font-semibold">Rationale: </span>
                  {selectedDecision.rationale.decision_rationale}
                </div>
                {selectedDecision.rationale.verification_plan && (
                  <div className="text-xs text-zinc-300">
                    <span className="text-zinc-500 font-semibold">Verification Plan: </span>
                    {selectedDecision.rationale.verification_plan}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* SUBTAB 4: DESIGN REVIEWS & GATING */}
        {subTab === "reviews" && (
          <div className="space-y-6 max-w-7xl mx-auto">
            {/* Review Selector */}
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider">Review Session:</span>
                <select
                  value={selectedReview?.id || ""}
                  onChange={(e) => {
                    const r = reviews.find((rev) => rev.id === e.target.value);
                    if (r) setSelectedReview(r);
                  }}
                  className="bg-zinc-900 border border-zinc-700 text-xs rounded px-2.5 py-1 text-zinc-200"
                >
                  {reviews.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title} ({r.status})
                    </option>
                  ))}
                </select>
                {selectedReview && (
                  <Badge variant="outline" className="text-[10px] border-cyan-800 text-cyan-300">
                    Status: {selectedReview.status}
                  </Badge>
                )}
              </div>

              {selectedReview && (
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleViewReport}
                    className="h-7 text-xs border-zinc-700 bg-zinc-800 text-zinc-200 hover:bg-zinc-700 flex items-center gap-1.5"
                  >
                    <FileCheck className="w-3 h-3 text-cyan-400" />
                    Audit Report
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleCloseReview}
                    disabled={selectedReview.status === "CLOSED" || reviewReadiness?.overall_status === "BLOCKED"}
                    className={`h-7 text-xs flex items-center gap-1.5 ${
                      reviewReadiness?.overall_status === "BLOCKED"
                        ? "bg-red-950 text-red-400 border border-red-800 cursor-not-allowed"
                        : "bg-emerald-600 hover:bg-emerald-500 text-white"
                    }`}
                  >
                    <Lock className="w-3 h-3" />
                    Close Review Session
                  </Button>
                </div>
              )}
            </div>

            {/* Categorical Review Readiness Banner */}
            {reviewReadiness && (
              <div
                className={`p-4 rounded-lg border flex items-start justify-between ${
                  reviewReadiness.overall_status === "READY"
                    ? "bg-emerald-950/20 border-emerald-800/60"
                    : reviewReadiness.overall_status === "BLOCKED"
                    ? "bg-red-950/25 border-red-800/80"
                    : "bg-amber-950/20 border-amber-800/60"
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    {reviewReadiness.overall_status === "READY" ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : reviewReadiness.overall_status === "BLOCKED" ? (
                      <AlertOctagon className="w-4 h-4 text-red-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                    )}
                    <span className="text-xs font-bold uppercase tracking-wider">
                      Design Review Readiness: {reviewReadiness.overall_status}
                    </span>
                  </div>
                  {reviewReadiness.blockers.length > 0 && (
                    <ul className="list-disc pl-5 text-xs text-red-300 space-y-0.5 pt-1">
                      {reviewReadiness.blockers.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="flex items-center gap-3 text-xs">
                  {Object.entries(reviewReadiness.dimensions).map(([dim, st]) => (
                    <div key={dim} className="flex flex-col items-center">
                      <span className="text-[10px] text-zinc-400 uppercase font-semibold">{dim}</span>
                      <Badge
                        variant="outline"
                        className={`text-[9px] py-0 h-4 mt-0.5 ${
                          st === "READY"
                            ? "border-emerald-800 text-emerald-400"
                            : st === "BLOCKED"
                            ? "border-red-800 text-red-400"
                            : "border-amber-800 text-amber-400"
                        }`}
                      >
                        {st}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Checkpoints & Findings Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Checkpoints */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                  Review Checkpoints ({selectedReview?.checkpoints?.length || 0})
                </h4>
                <div className="space-y-2">
                  {selectedReview?.checkpoints?.map((chk) => (
                    <div key={chk.id} className="p-3 rounded bg-zinc-900/60 border border-zinc-800 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <span className="text-xs font-medium text-zinc-200">{chk.checkpoint_name}</span>
                        {chk.notes && <p className="text-[11px] text-zinc-500">{chk.notes}</p>}
                      </div>
                      <Badge
                        className={`text-[10px] ${
                          chk.status === "PASS"
                            ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                            : chk.status === "FAIL"
                            ? "bg-red-950 text-red-300 border-red-800"
                            : "bg-zinc-800 text-zinc-400 border-zinc-700"
                        }`}
                      >
                        {chk.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>

              {/* Engineering Findings & Waivers */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                  <AlertOctagon className="w-3.5 h-3.5 text-red-400" />
                  Engineering Findings ({selectedReview?.findings?.length || 0})
                </h4>
                <div className="space-y-2">
                  {selectedReview?.findings?.map((f) => (
                    <div key={f.id} className="p-3 rounded bg-zinc-900/60 border border-zinc-800 space-y-2">
                      <div className="flex items-start justify-between">
                        <div className="space-y-0.5">
                          <span className="text-xs font-medium text-zinc-200">{f.description}</span>
                          <div className="text-[10px] text-zinc-500 font-mono">Source: {f.source_analysis || "N/A"}</div>
                        </div>
                        <Badge
                          className={`text-[10px] ml-2 shrink-0 ${
                            f.severity === "BLOCKER" || f.severity === "CRITICAL"
                              ? "bg-red-950 text-red-300 border-red-800"
                              : "bg-amber-950 text-amber-300 border-amber-800"
                          }`}
                        >
                          {f.severity}
                        </Badge>
                      </div>

                      <div className="flex items-center justify-between text-[11px] pt-1 border-t border-zinc-800/80">
                        <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                          {f.status}
                        </Badge>
                        {f.status === "OPEN" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setWaiveFindingId(f.id)}
                            className="h-6 text-[10px] border-amber-800/80 text-amber-300 hover:bg-amber-950"
                          >
                            Waive Finding
                          </Button>
                        )}
                        {f.status === "WAIVED" && (
                          <span className="text-[10px] text-amber-400 italic">Waived: {f.waiver_rationale}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Questions & Unknowns */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
                Unresolved Questions & Blocking Unknowns ({reviewQuestions.length})
              </h4>
              <div className="space-y-2">
                {reviewQuestions.map((q) => (
                  <div key={q.id} className="p-3 rounded bg-zinc-900/60 border border-zinc-800 space-y-1.5">
                    <div className="flex items-start justify-between">
                      <div className="space-y-0.5">
                        <span className="text-xs font-medium text-zinc-200">{q.question}</span>
                        {q.reason && <p className="text-[11px] text-zinc-500">Reason: {q.reason}</p>}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {q.blocking && (
                          <Badge className="text-[10px] bg-red-950 text-red-300 border-red-800">BLOCKING</Badge>
                        )}
                        <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
                          {q.status}
                        </Badge>
                      </div>
                    </div>
                    {q.status === "OPEN" && (
                      <div className="pt-1 flex items-center gap-2">
                        {answeringQuestionId === q.id ? (
                          <div className="flex items-center gap-2 w-full">
                            <input
                              type="text"
                              value={questionAnswer}
                              onChange={(e) => setQuestionAnswer(e.target.value)}
                              placeholder="Enter engineer answer with evidence..."
                              className="bg-zinc-950 border border-zinc-700 text-xs rounded px-2.5 py-1 text-zinc-200 flex-1"
                            />
                            <Button size="sm" onClick={() => handleAnswerQuestion(q.id)} className="h-7 text-xs bg-emerald-600">
                              Submit
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setAnsweringQuestionId(null)} className="h-7 text-xs">
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setAnsweringQuestionId(q.id)}
                            className="h-6 text-[10px] border-zinc-700 text-zinc-300"
                          >
                            Answer Question
                          </Button>
                        )}
                      </div>
                    )}
                    {q.status === "ANSWERED" && (
                      <div className="text-[11px] text-emerald-300/90 pt-1 border-t border-zinc-800/80">
                        Answer: {q.answer}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Human Alternative Selection Modal */}
      {isSelectingAlt && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <form
            onSubmit={handleConfirmAlternativeSelection}
            className="w-full max-w-xl bg-zinc-900 border border-zinc-700 rounded-lg p-5 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-emerald-400" />
                Engineer Alternative Selection Authority
              </h3>
              <button
                type="button"
                onClick={() => setIsSelectingAlt(false)}
                className="text-zinc-500 hover:text-zinc-300"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-zinc-400 font-semibold block mb-1">
                  Decision Rationale (Mandatory Engineering Justification):
                </label>
                <textarea
                  required
                  rows={3}
                  value={selectionRationale}
                  onChange={(e) => setSelectionRationale(e.target.value)}
                  placeholder="Explain why this alternative is selected over competing options..."
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Key Satisfied Requirements (comma separated):</label>
                <input
                  type="text"
                  value={selectionKeyReqs}
                  onChange={(e) => setSelectionKeyReqs(e.target.value)}
                  placeholder="e.g. REQ-SYS-001, REQ-SYS-002"
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Accepted Trade-offs:</label>
                <input
                  type="text"
                  value={selectionTradeoffs}
                  onChange={(e) => setSelectionTradeoffs(e.target.value)}
                  placeholder="e.g. Increased EMI filtering footprint"
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Accepted Unknowns (explicit human waiver):</label>
                <input
                  type="text"
                  value={selectionUnknowns}
                  onChange={(e) => setSelectionUnknowns(e.target.value)}
                  placeholder="e.g. Board parasitic resonance will be measured during proto spin"
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                />
              </div>

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Verification Plan:</label>
                <input
                  type="text"
                  value={selectionVerification}
                  onChange={(e) => setSelectionVerification(e.target.value)}
                  placeholder="e.g. Execute phase margin sweep and EMI chamber test on prototype rev A"
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
              <Button type="button" variant="outline" onClick={() => setIsSelectingAlt(false)} className="text-xs">
                Cancel
              </Button>
              <Button type="submit" className="text-xs bg-emerald-600 hover:bg-emerald-500">
                Confirm Human Selection
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Waive Finding Modal */}
      {waiveFindingId && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-lg p-5 space-y-4 shadow-xl">
            <h3 className="text-sm font-bold text-amber-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Waive Engineering Finding
            </h3>
            <p className="text-xs text-zinc-400">
              Waiving a finding overrides the blocker gating. A technical waiver justification is mandatory.
            </p>
            <textarea
              rows={3}
              value={waiverRationale}
              onChange={(e) => setWaiverRationale(e.target.value)}
              placeholder="Provide technical rationale for why this finding can be safely waived..."
              className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-xs text-zinc-200"
            />
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
              <Button size="sm" variant="outline" onClick={() => setWaiveFindingId(null)} className="text-xs">
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => handleWaiveFinding(waiveFindingId)}
                className="text-xs bg-amber-600 hover:bg-amber-500 text-white"
              >
                Confirm Waiver
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Create Requirement Modal */}
      {isCreatingReq && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <form
            onSubmit={handleCreateRequirement}
            className="w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-lg p-5 space-y-3 shadow-xl text-xs"
          >
            <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              <FileText className="w-4 h-4 text-emerald-400" />
              Add Engineering Requirement
            </h3>
            <div>
              <label className="text-zinc-400 block mb-1">Requirement Key:</label>
              <input
                required
                type="text"
                value={newReqKey}
                onChange={(e) => setNewReqKey(e.target.value)}
                placeholder="e.g. REQ-SYS-001"
                className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">Title:</label>
              <input
                required
                type="text"
                value={newReqTitle}
                onChange={(e) => setNewReqTitle(e.target.value)}
                placeholder="e.g. Maximum Quiescent Current"
                className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
              />
            </div>
            <div>
              <label className="text-zinc-400 block mb-1">Statement (The system shall...):</label>
              <textarea
                required
                rows={2}
                value={newReqStatement}
                onChange={(e) => setNewReqStatement(e.target.value)}
                placeholder="Formal requirement statement..."
                className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-zinc-400 block mb-1">Category:</label>
                <select
                  value={newReqCategory}
                  onChange={(e) => setNewReqCategory(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                >
                  <option value="FUNCTIONAL">FUNCTIONAL</option>
                  <option value="ELECTRICAL">ELECTRICAL</option>
                  <option value="THERMAL">THERMAL</option>
                  <option value="INTERFACE">INTERFACE</option>
                  <option value="SAFETY">SAFETY</option>
                  <option value="COMPLIANCE">COMPLIANCE</option>
                </select>
              </div>
              <div>
                <label className="text-zinc-400 block mb-1">Priority:</label>
                <select
                  value={newReqPriority}
                  onChange={(e) => setNewReqPriority(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
                >
                  <option value="SHALL">SHALL (Mandatory)</option>
                  <option value="SHOULD">SHOULD (Desirable)</option>
                  <option value="MAY">MAY (Optional)</option>
                </select>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
              <Button type="button" variant="outline" onClick={() => setIsCreatingReq(false)} className="text-xs">
                Cancel
              </Button>
              <Button type="submit" className="text-xs bg-emerald-600 hover:bg-emerald-500">
                Create Requirement
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Create Baseline Modal */}
      {isCreatingBaseline && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <form
            onSubmit={handleCreateBaseline}
            className="w-full max-w-md bg-zinc-900 border border-zinc-700 rounded-lg p-5 space-y-3 shadow-xl text-xs"
          >
            <h3 className="text-sm font-bold text-cyan-300 flex items-center gap-2">
              <Bookmark className="w-4 h-4 text-cyan-400" />
              Freeze Requirement Baseline
            </h3>
            <p className="text-zinc-400">
              Freezing a baseline computes a SHA-256 hash across all active requirements bound to system revision {system.revision}.
            </p>
            <div>
              <label className="text-zinc-400 block mb-1">Baseline Name:</label>
              <input
                required
                type="text"
                value={newBaselineName}
                onChange={(e) => setNewBaselineName(e.target.value)}
                placeholder="e.g. CDR Freeze 1.0"
                className="w-full bg-zinc-950 border border-zinc-700 rounded p-2 text-zinc-200"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-3 border-t border-zinc-800">
              <Button type="button" variant="outline" onClick={() => setIsCreatingBaseline(false)} className="text-xs">
                Cancel
              </Button>
              <Button type="submit" className="text-xs bg-cyan-600 hover:bg-cyan-500">
                Freeze Baseline
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Audit Report Modal */}
      {reviewReport && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-6">
          <div className="w-full max-w-3xl bg-zinc-900 border border-zinc-700 rounded-lg p-6 space-y-4 shadow-2xl max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-emerald-400" />
                Design Review Audit Report — {reviewReport.title}
              </h3>
              <button onClick={() => setReviewReport(null)} className="text-zinc-500 hover:text-zinc-300 text-lg">
                &times;
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-3 gap-3 p-3 rounded bg-zinc-950 border border-zinc-800">
                <div>
                  <span className="text-zinc-500 block text-[10px]">Status:</span>
                  <span className="font-bold text-zinc-200">{reviewReport.status}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">System Revision:</span>
                  <span className="font-bold text-zinc-200">Rev {reviewReport.system_revision}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px]">Total Requirements:</span>
                  <span className="font-bold text-zinc-200">{reviewReport.requirements_count}</span>
                </div>
              </div>

              {reviewReport.decision?.selected_alternative_id && (
                <div className="p-3 rounded bg-emerald-950/20 border border-emerald-900/50 space-y-1">
                  <span className="text-xs font-bold text-emerald-300">Selected Alternative:</span>
                  <p className="text-zinc-300">{reviewReport.decision.rationale?.decision_rationale}</p>
                </div>
              )}

              <div>
                <span className="text-zinc-400 font-semibold block mb-1">Checkpoints Summary:</span>
                <div className="space-y-1">
                  {reviewReport.checkpoints_summary?.map((c: any, i: number) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded bg-zinc-950">
                      <span>{c.name}</span>
                      <Badge variant="outline" className="text-[9px]">{c.status}</Badge>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <span className="text-zinc-400 font-semibold block mb-1">Findings Summary:</span>
                <div className="flex items-center gap-3 p-2 rounded bg-zinc-950">
                  <span>Total: {reviewReport.findings_summary?.total || 0}</span>
                  <span className="text-amber-400">Waived: {reviewReport.findings_summary?.waived || 0}</span>
                  <span className="text-red-400">Critical: {reviewReport.findings_summary?.critical || 0}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end pt-3 border-t border-zinc-800">
              <Button size="sm" onClick={() => setReviewReport(null)} className="text-xs">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
