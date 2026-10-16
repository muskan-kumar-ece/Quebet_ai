"use client";

import React, { useState, useEffect } from "react";
import {
  BookOpen,
  Search,
  Filter,
  ShieldCheck,
  AlertTriangle,
  FileText,
  Hash,
  Database,
  ArrowRight,
  RefreshCw,
  GitCommit,
  ExternalLink,
  Layers,
  ChevronDown,
  ChevronRight,
  Info,
  Cpu,
  Zap,
  AlertOctagon,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Thermometer,
  Activity,
  Sliders,
  Component,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { apiClient } from "@/lib/api";

export type KnowledgeClassification =
  | "AUTHORITATIVE_SOURCE"
  | "DERIVED_ENGINEERING_FACT"
  | "CALCULATED_RESULT"
  | "HISTORICAL_EXPERIENCE"
  | "AI_GENERATED_EXPLANATION"
  | "USER_ASSERTION"
  | "UNKNOWN";

export interface KnowledgeRecord {
  id: string;
  source_id: string | null;
  domain: string;
  subject_type: string;
  subject_identifier: string;
  parameter: string;
  value: string;
  unit: string | null;
  classification: KnowledgeClassification;
  parameter_category?: string | null;
  raw_value: string | null;
  normalized_value: number | null;
  source_location: {
    page?: number;
    section?: string;
    table?: string;
    figure?: string;
    [key: string]: any;
  };
  is_conflicting: boolean;
  conflict_details: {
    status?: string;
    conflicting_record_id?: string;
    conflicting_source_id?: string;
    conflicting_raw_value?: string;
    conflicting_normalized_value?: number;
    delta_ratio?: number;
    description?: string;
    [key: string]: any;
  };
  conditions: Record<string, any>;
  valid_range?: { min?: number; max?: number } | null;
  status: string;
  created_at: string;
}

export interface SourceDocument {
  id: string;
  title: string;
  publisher: string;
  document_identifier: string;
  revision: string;
  version: string;
  document_hash: string | null;
  trust_level: string;
  status: string;
  source_type: string;
  uri?: string | null;
}

export interface KnowledgeSearchItem {
  record: KnowledgeRecord;
  source: SourceDocument | null;
  provenance_chain: {
    source_id?: string | null;
    document_identifier?: string | null;
    revision?: string | null;
    integrity_digest?: string | null;
    source_location?: Record<string, any>;
    classification?: string;
    precedence_rank?: number;
    is_conflicting?: boolean;
    conflict_details?: Record<string, any>;
  };
}

export type IdentityState = "RESOLVED" | "AMBIGUOUS" | "UNKNOWN" | "CONFLICTING";
export type ApplicabilityCategory =
  | "APPLICABLE"
  | "POTENTIALLY_APPLICABLE"
  | "NOT_APPLICABLE"
  | "UNKNOWN"
  | "CONFLICTING";

export interface ComponentIdentity {
  state: IdentityState;
  manufacturer?: string | null;
  part_number?: string | null;
  manufacturer_part_number?: string | null;
  component_type?: string | null;
  package?: string | null;
  variant?: string | null;
  document_identifier?: string | null;
  revision?: string | null;
  source_id?: string | null;
  candidates?: Array<Record<string, any>>;
  ambiguity_reasons?: string[];
}

export interface ComponentPin {
  pin_number: string;
  pin_name: string;
  pin_type: string;
  electrical_role?: string | null;
  description?: string | null;
  source_location?: Record<string, any>;
}

export interface ComponentParameterItem {
  parameter: string;
  category: string;
  raw_value: string;
  normalized_value?: number | null;
  unit?: string | null;
  conditions?: Record<string, any>;
  valid_range?: { min?: number; max?: number } | null;
  classification: string;
  source_id?: string | null;
  source_revision?: string | null;
  source_location?: Record<string, any>;
  is_conflicting?: boolean;
  conflict_details?: Record<string, any>;
}

export interface ComponentConstraintItem {
  constraint_type: string;
  description: string;
  parameter?: string | null;
  requirement_value?: string | null;
  conditions?: Record<string, any>;
  source_location?: Record<string, any>;
}

export interface ComponentReferenceDesignItem {
  title: string;
  topology: string;
  description?: string | null;
  external_components?: Array<{ ref_des?: string; value?: string; description?: string }>;
  source_location?: Record<string, any>;
  provenance?: Record<string, any>;
}

export interface ComponentProfileResponse {
  identity: ComponentIdentity;
  pins: ComponentPin[];
  operating_ranges: ComponentParameterItem[];
  absolute_maximums: ComponentParameterItem[];
  electrical_characteristics: ComponentParameterItem[];
  thermal_characteristics: ComponentParameterItem[];
  application_constraints: ComponentConstraintItem[];
  reference_designs: ComponentReferenceDesignItem[];
  contradictions: Array<Record<string, any>>;
  unknowns: string[];
  provenance_chain: Record<string, any>;
}

export interface OperatingValidationResponse {
  parameter: string;
  evaluated_value: number;
  is_operating_valid: boolean;
  is_absolute_maximum_exceeded: boolean;
  status: "OPERATING_POINT_VALID" | "OPERATING_LIMIT_EXCEEDED" | "ABSOLUTE_MAXIMUM_EXCEEDED" | "PARAMETER_UNKNOWN";
  operating_range?: { min?: number; max?: number; raw?: string } | null;
  absolute_maximum?: { max?: number; raw?: string } | null;
  explanation: string;
}

export interface ApplicabilityEvaluationResponse {
  part_number: string;
  status: ApplicabilityCategory;
  reasons: string[];
  evaluated_conditions: Record<string, any>;
  missing_conditions: string[];
}

interface KnowledgeInspectorProps {
  initialSubject?: string;
}

const CLASSIFICATION_CONFIG: Record<
  KnowledgeClassification,
  { label: string; bg: string; text: string; border: string; rank: number }
> = {
  AUTHORITATIVE_SOURCE: {
    label: "Authoritative Source",
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/30",
    rank: 1,
  },
  DERIVED_ENGINEERING_FACT: {
    label: "Derived Fact",
    bg: "bg-cyan-500/10",
    text: "text-cyan-400",
    border: "border-cyan-500/30",
    rank: 2,
  },
  CALCULATED_RESULT: {
    label: "Calculated Result",
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    border: "border-blue-500/30",
    rank: 3,
  },
  HISTORICAL_EXPERIENCE: {
    label: "Historical Experience",
    bg: "bg-purple-500/10",
    text: "text-purple-400",
    border: "border-purple-500/30",
    rank: 4,
  },
  USER_ASSERTION: {
    label: "User Assertion",
    bg: "bg-zinc-500/10",
    text: "text-zinc-400",
    border: "border-zinc-500/30",
    rank: 5,
  },
  AI_GENERATED_EXPLANATION: {
    label: "AI Explanation (Non-Authoritative)",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    border: "border-amber-500/30",
    rank: 6,
  },
  UNKNOWN: {
    label: "Unknown / Missing",
    bg: "bg-rose-500/10",
    text: "text-rose-400",
    border: "border-rose-500/30",
    rank: 7,
  },
};

export const KnowledgeInspector: React.FC<KnowledgeInspectorProps> = ({ initialSubject = "" }) => {
  const [activeTab, setActiveTab] = useState<"records" | "profile">("records");

  // Knowledge Records state
  const [searchQuery, setSearchQuery] = useState(initialSubject);
  const [selectedClassification, setSelectedClassification] = useState<string>("ALL");
  const [showConflictsOnly, setShowConflictsOnly] = useState<boolean>(false);
  const [items, setItems] = useState<KnowledgeSearchItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRecordId, setExpandedRecordId] = useState<string | null>(null);

  // Component Profile state
  const [componentQuery, setComponentQuery] = useState<string>(initialSubject || "LM317");
  const [componentProfile, setComponentProfile] = useState<ComponentProfileResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState<boolean>(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Interactive Validator state
  const [valParam, setValParam] = useState<string>("input_voltage");
  const [valNumber, setValNumber] = useState<string>("5.8");
  const [valUnit, setValUnit] = useState<string>("V");
  const [valResult, setValResult] = useState<OperatingValidationResponse | null>(null);
  const [valLoading, setValLoading] = useState<boolean>(false);

  // Applicability state
  const [appContextJson, setAppContextJson] = useState<string>(
    JSON.stringify({ input_voltage: 12.0, ambient_temperature: 45.0 }, null, 2)
  );
  const [appResult, setAppResult] = useState<ApplicabilityEvaluationResponse | null>(null);
  const [appLoading, setAppLoading] = useState<boolean>(false);

  const fetchKnowledge = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, any> = { limit: 100 };
      if (searchQuery.trim()) {
        params.q = searchQuery.trim();
      }
      if (selectedClassification !== "ALL") {
        params.classification = selectedClassification;
      }
      const response = await apiClient.get("/knowledge/search", { params });
      const data = response.data?.data;
      if (data && Array.isArray(data.items)) {
        setItems(data.items);
      } else {
        setItems([]);
      }
    } catch (err: any) {
      console.error("Failed to load knowledge records:", err);
      setError(err?.response?.data?.detail || "Failed to retrieve engineering knowledge");
    } finally {
      setIsLoading(false);
    }
  };

  const loadComponentProfile = async (targetPart: string) => {
    if (!targetPart.trim()) return;
    setProfileLoading(true);
    setProfileError(null);
    setValResult(null);
    setAppResult(null);
    try {
      const res = await apiClient.get(`/knowledge/components/${encodeURIComponent(targetPart.trim())}/profile`);
      if (res.data?.data) {
        setComponentProfile(res.data.data);
      } else {
        setProfileError("No profile data returned for this component");
      }
    } catch (err: any) {
      console.error("Failed to load component profile:", err);
      setProfileError(err?.response?.data?.detail || `Failed to fetch profile for ${targetPart}`);
    } finally {
      setProfileLoading(false);
    }
  };

  const handleValidateOperating = async () => {
    if (!componentProfile?.identity?.part_number || !valParam.trim() || isNaN(Number(valNumber))) return;
    setValLoading(true);
    try {
      const res = await apiClient.post(
        `/knowledge/components/${encodeURIComponent(componentProfile.identity.part_number)}/validate-operating`,
        {
          parameter: valParam.trim(),
          value: parseFloat(valNumber),
          unit: valUnit.trim() || null,
        }
      );
      if (res.data?.data) {
        setValResult(res.data.data);
      }
    } catch (err: any) {
      console.error("Validation request failed:", err);
      setProfileError(err?.response?.data?.detail || "Operating point validation failed");
    } finally {
      setValLoading(false);
    }
  };

  const handleEvaluateApplicability = async () => {
    if (!componentProfile?.identity?.part_number) return;
    setAppLoading(true);
    try {
      const parsedContext = JSON.parse(appContextJson);
      const res = await apiClient.post(
        `/knowledge/components/${encodeURIComponent(componentProfile.identity.part_number)}/applicability`,
        { context: parsedContext }
      );
      if (res.data?.data) {
        setAppResult(res.data.data);
      }
    } catch (err: any) {
      console.error("Applicability evaluation failed:", err);
      setProfileError(err?.message || "Invalid JSON or evaluation failure");
    } finally {
      setAppLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "records") {
      fetchKnowledge();
    } else if (activeTab === "profile" && componentQuery) {
      loadComponentProfile(componentQuery);
    }
  }, [activeTab, selectedClassification]);

  const filteredItems = items.filter((item) => {
    if (showConflictsOnly && !item.record.is_conflicting) {
      return false;
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-6 p-6 bg-zinc-950 text-zinc-100 min-h-screen">
      {/* Header & Core Invariants */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Component & Knowledge Intelligence</h1>
              <p className="text-xs text-zinc-400">
                Authoritative datasheet profiles, operating ranges vs absolute maximums, and deterministic validation.
              </p>
            </div>
          </div>
        </div>

        {/* Invariant Pills */}
        <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono">
          <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400">
            OPERATING LIMIT != ABSOLUTE MAX
          </span>
          <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400">
            TEST CONDITIONS != CONTRADICTIONS
          </span>
          <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400">
            ZERO SYNTHETIC SCORING
          </span>
          <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-zinc-400">
            NO WINNER PICKING
          </span>
        </div>
      </div>

      {/* Main Mode Navigation Tabs */}
      <div className="flex items-center gap-3 border-b border-zinc-800 pb-1">
        <button
          onClick={() => setActiveTab("records")}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 text-xs font-medium transition-colors ${
            activeTab === "records"
              ? "border-emerald-500 text-emerald-400 bg-emerald-500/5 rounded-t"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Knowledge Records & Sources
        </button>

        <button
          onClick={() => {
            setActiveTab("profile");
            if (!componentProfile) loadComponentProfile(componentQuery);
          }}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 text-xs font-medium transition-colors ${
            activeTab === "profile"
              ? "border-emerald-500 text-emerald-400 bg-emerald-500/5 rounded-t"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Component className="w-4 h-4" />
          Component Profile & Limits (Wave 2)
        </button>
      </div>

      {/* ========================================================================= */}
      {/* MODE 1: KNOWLEDGE RECORDS & SOURCES                                       */}
      {/* ========================================================================= */}
      {activeTab === "records" && (
        <div className="flex flex-col gap-5">
          {/* Control Bar: Search & Classification Filters */}
          <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && fetchKnowledge()}
                placeholder="Search component identifier, parameter, or value (e.g. LM317, v_ref, 10uF)..."
                className="pl-9 bg-zinc-900 border-zinc-800 text-xs text-zinc-200 placeholder:text-zinc-500 h-9 rounded-md focus-visible:ring-emerald-500/40"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchKnowledge}
                disabled={isLoading}
                className="h-9 px-3 border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-xs text-zinc-200"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? "animate-spin" : ""}`} />
                Query
              </Button>

              <Button
                variant={showConflictsOnly ? "destructive" : "outline"}
                size="sm"
                onClick={() => setShowConflictsOnly(!showConflictsOnly)}
                className={`h-9 px-3 text-xs ${
                  showConflictsOnly
                    ? "bg-rose-950 border-rose-800 text-rose-300 hover:bg-rose-900"
                    : "border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-zinc-200"
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
                Conflicts Only
              </Button>
            </div>
          </div>

          {/* Classification Quick Filter Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
            <button
              onClick={() => setSelectedClassification("ALL")}
              className={`px-3 py-1 rounded-md transition-colors ${
                selectedClassification === "ALL"
                  ? "bg-zinc-800 text-zinc-100 font-medium"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
              }`}
            >
              All Classes ({items.length})
            </button>
            {Object.entries(CLASSIFICATION_CONFIG).map(([key, config]) => {
              const count = items.filter((i) => i.record.classification === key).length;
              const isSelected = selectedClassification === key;
              return (
                <button
                  key={key}
                  onClick={() => setSelectedClassification(key)}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-colors ${
                    isSelected
                      ? `${config.bg} ${config.text} border ${config.border} font-medium`
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                  }`}
                >
                  <span>{config.label}</span>
                  <span className="text-[10px] opacity-75 font-mono">({count})</span>
                </button>
              );
            })}
          </div>

          {/* Error state */}
          {error && (
            <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-md text-xs text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Records Table */}
          <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm overflow-hidden">
            <CardHeader className="p-4 border-b border-zinc-800/80 bg-zinc-900/80 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-medium text-zinc-200">
                  Structured Engineering Facts & Specifications
                </CardTitle>
                <CardDescription className="text-xs text-zinc-400">
                  Showing {filteredItems.length} records ordered by authoritative precedence rank
                </CardDescription>
              </div>
              <Badge variant="outline" className="text-[10px] font-mono border-zinc-800 text-zinc-400">
                {filteredItems.length} Records
              </Badge>
            </CardHeader>

            <CardContent className="p-0">
              {filteredItems.length === 0 ? (
                <div className="py-16 text-center text-xs text-zinc-500">
                  No engineering knowledge records found matching your filters.
                </div>
              ) : (
                <div className="divide-y divide-zinc-800/60">
                  {filteredItems.map((item) => {
                    const rec = item.record;
                    const src = item.source;
                    const isExpanded = expandedRecordId === rec.id;
                    const classConf =
                      CLASSIFICATION_CONFIG[rec.classification] ||
                      CLASSIFICATION_CONFIG.AUTHORITATIVE_SOURCE;

                    return (
                      <div key={rec.id} className="transition-colors hover:bg-zinc-800/30">
                        <div
                          className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer"
                          onClick={() => setExpandedRecordId(isExpanded ? null : rec.id)}
                        >
                          {/* Left: Component & Parameter */}
                          <div className="flex items-start gap-3">
                            <button className="mt-0.5 text-zinc-500 hover:text-zinc-300">
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </button>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-semibold text-sm text-zinc-100">
                                  {rec.subject_identifier}
                                </span>
                                <span className="text-xs text-zinc-400 font-mono">
                                  / {rec.parameter}
                                </span>
                                {rec.parameter_category && (
                                  <Badge variant="secondary" className="text-[9px] font-mono bg-zinc-800 text-zinc-300">
                                    {rec.parameter_category}
                                  </Badge>
                                )}
                                <Badge
                                  variant="outline"
                                  className={`text-[10px] font-mono ${classConf.bg} ${classConf.text} ${classConf.border}`}
                                >
                                  Rank #{classConf.rank}: {classConf.label}
                                </Badge>

                                {rec.is_conflicting && (
                                  <Badge
                                    variant="destructive"
                                    className="text-[10px] font-mono bg-rose-500/20 text-rose-300 border-rose-500/40"
                                  >
                                    CONTRADICTORY_SOURCE_DATA
                                  </Badge>
                                )}
                              </div>

                              <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400">
                                {src ? (
                                  <span className="flex items-center gap-1 font-mono text-[11px]">
                                    <FileText className="w-3 h-3 text-zinc-500" />
                                    {src.publisher} — {src.document_identifier} ({src.revision})
                                  </span>
                                ) : (
                                  <span className="text-zinc-500 italic">No linked source document</span>
                                )}

                                {rec.source_location && Object.keys(rec.source_location).length > 0 && (
                                  <span className="text-[11px] text-zinc-500">
                                    Loc:{" "}
                                    {rec.source_location.page ? `p.${rec.source_location.page} ` : ""}
                                    {rec.source_location.table || rec.source_location.section || ""}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Right: Values & Units */}
                          <div className="flex items-center gap-6 md:text-right shrink-0">
                            <div>
                              <div className="text-sm font-medium text-emerald-400 font-mono">
                                {rec.raw_value || rec.value} {rec.unit || ""}
                              </div>
                              {rec.normalized_value !== null && rec.normalized_value !== undefined && (
                                <div className="text-[11px] text-zinc-400 font-mono">
                                  SI Norm: {rec.normalized_value} {rec.unit || ""}
                                </div>
                              )}
                            </div>

                            {src?.document_hash && (
                              <div className="hidden lg:block text-right">
                                <div className="flex items-center gap-1 text-[10px] font-mono text-zinc-500">
                                  <ShieldCheck className="w-3 h-3 text-emerald-500" />
                                  SHA-256
                                </div>
                                <div className="text-[10px] font-mono text-zinc-400 truncate w-24">
                                  {src.document_hash.slice(0, 10)}...
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Expanded Detail Tray */}
                        {isExpanded && (
                          <div className="px-10 pb-4 pt-1 bg-zinc-950/60 border-t border-zinc-800/40 text-xs">
                            {rec.is_conflicting && (
                              <div className="mb-3 p-3 bg-rose-950/40 border border-rose-800/50 rounded text-rose-200">
                                <div className="flex items-center gap-1.5 font-semibold text-rose-300">
                                  <AlertTriangle className="w-3.5 h-3.5" />
                                  Contradictory Source Data Warning
                                </div>
                                <p className="mt-1 text-xs text-rose-300/90">
                                  {rec.conflict_details?.description ||
                                    "This parameter has conflicting ratings across multiple authoritative or historical records."}
                                </p>
                                {rec.conflict_details?.delta_ratio && (
                                  <div className="mt-1 font-mono text-[11px] text-rose-400">
                                    Discrepancy delta: {(rec.conflict_details.delta_ratio * 100).toFixed(1)}%
                                  </div>
                                )}
                              </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 py-2">
                              {/* Provenance Binding */}
                              <div className="p-3 bg-zinc-900 border border-zinc-800 rounded">
                                <div className="font-semibold text-zinc-300 flex items-center gap-1.5 mb-1.5">
                                  <GitCommit className="w-3.5 h-3.5 text-zinc-400" />
                                  Provenance Chain
                                </div>
                                <div className="space-y-1 font-mono text-[11px] text-zinc-400">
                                  <div>Record ID: {rec.id}</div>
                                  <div>Status: {rec.status}</div>
                                  <div>Domain: {rec.domain}</div>
                                  <div>Type: {rec.subject_type}</div>
                                </div>
                              </div>

                              {/* Source Details */}
                              <div className="p-3 bg-zinc-900 border border-zinc-800 rounded">
                                <div className="font-semibold text-zinc-300 flex items-center gap-1.5 mb-1.5">
                                  <FileText className="w-3.5 h-3.5 text-zinc-400" />
                                  Authoritative Source
                                </div>
                                {src ? (
                                  <div className="space-y-1 text-[11px] text-zinc-400">
                                    <div>Title: {src.title}</div>
                                    <div>Doc ID: {src.document_identifier}</div>
                                    <div>Revision: {src.revision}</div>
                                    <div>Trust Level: {src.trust_level}</div>
                                    <div className="font-mono text-[10px] break-all text-zinc-500">
                                      Digest: {src.document_hash}
                                    </div>
                                  </div>
                                ) : (
                                  <div className="text-zinc-500">No source bound</div>
                                )}
                              </div>

                              {/* Conditions & Validity */}
                              <div className="p-3 bg-zinc-900 border border-zinc-800 rounded">
                                <div className="font-semibold text-zinc-300 flex items-center gap-1.5 mb-1.5">
                                  <Layers className="w-3.5 h-3.5 text-zinc-400" />
                                  Operating Conditions
                                </div>
                                {rec.conditions && Object.keys(rec.conditions).length > 0 ? (
                                  <pre className="text-[10px] font-mono text-zinc-400 bg-zinc-950 p-2 rounded overflow-x-auto">
                                    {JSON.stringify(rec.conditions, null, 2)}
                                  </pre>
                                ) : (
                                  <div className="text-zinc-500 text-[11px]">Unconditional / Standard Test Conditions</div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODE 2: COMPONENT PROFILE & LIMITS (WAVE 2)                               */}
      {/* ========================================================================= */}
      {activeTab === "profile" && (
        <div className="flex flex-col gap-6">
          {/* Query & Resolver Header */}
          <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
            <div className="relative flex-1">
              <Cpu className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <Input
                value={componentQuery}
                onChange={(e) => setComponentQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadComponentProfile(componentQuery)}
                placeholder="Enter Component Part Number (e.g. LM317, TPS5430, ESP32)..."
                className="pl-9 bg-zinc-900 border-zinc-800 text-xs text-zinc-200 placeholder:text-zinc-500 h-9 rounded-md focus-visible:ring-emerald-500/40"
              />
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => loadComponentProfile(componentQuery)}
              disabled={profileLoading}
              className="h-9 px-4 border-zinc-800 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 text-xs border border-emerald-500/30"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${profileLoading ? "animate-spin" : ""}`} />
              Resolve & Inspect Profile
            </Button>

            {/* Quick chips */}
            <div className="flex items-center gap-1.5">
              {["LM317", "TPS5430", "ESP32"].map((chip) => (
                <button
                  key={chip}
                  onClick={() => {
                    setComponentQuery(chip);
                    loadComponentProfile(chip);
                  }}
                  className="px-2.5 py-1 text-[11px] font-mono bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded text-zinc-300"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>

          {/* Profile Error */}
          {profileError && (
            <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-md text-xs text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{profileError}</span>
            </div>
          )}

          {/* If Profile Loaded */}
          {componentProfile && (
            <div className="flex flex-col gap-6">
              {/* Identity & Header Status */}
              <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm">
                <CardHeader className="p-4 border-b border-zinc-800/80 bg-zinc-900/80 flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded bg-zinc-800 text-zinc-200 border border-zinc-700">
                      <Component className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold text-zinc-100">
                          {componentProfile.identity.part_number || componentQuery}
                        </h2>
                        {componentProfile.identity.manufacturer && (
                          <span className="text-xs text-zinc-400 font-normal">
                            ({componentProfile.identity.manufacturer})
                          </span>
                        )}
                        <Badge
                          variant="outline"
                          className={`text-[10px] font-mono ${
                            componentProfile.identity.state === "RESOLVED"
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                              : componentProfile.identity.state === "AMBIGUOUS"
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                              : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                          }`}
                        >
                          Identity: {componentProfile.identity.state}
                        </Badge>
                      </div>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        Type: {componentProfile.identity.component_type || "Generic IC"} | Package:{" "}
                        {componentProfile.identity.package || "N/A"} | Revision:{" "}
                        {componentProfile.identity.revision || "Initial"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
                    <span className="px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded">
                      Doc ID: {componentProfile.identity.document_identifier || "BOUND_PRIMARY"}
                    </span>
                  </div>
                </CardHeader>

                {/* Ambiguity Alert if state is AMBIGUOUS */}
                {componentProfile.identity.state === "AMBIGUOUS" && (
                  <div className="p-4 bg-amber-950/30 border-b border-amber-800/40 text-amber-200 text-xs">
                    <div className="flex items-center gap-2 font-semibold text-amber-400 mb-1">
                      <AlertTriangle className="w-4 h-4" />
                      Ambiguous Part Number Match (Deterministic Non-Autocorrect)
                    </div>
                    <p className="text-zinc-300">
                      Multiple candidate components matched query &ldquo;{componentQuery}&rdquo;. Autonomous winner
                      picking is strictly disabled. Please refine with specific manufacturer or package.
                    </p>
                    {componentProfile.identity.ambiguity_reasons && (
                      <ul className="mt-2 list-disc list-inside space-y-0.5 text-zinc-400">
                        {componentProfile.identity.ambiguity_reasons.map((reason, idx) => (
                          <li key={idx}>{reason}</li>
                        ))}
                      </ul>
                    )}
                    {componentProfile.identity.candidates && componentProfile.identity.candidates.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {componentProfile.identity.candidates.map((cand, idx) => (
                          <div
                            key={idx}
                            className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-700 text-zinc-300 font-mono text-[11px]"
                          >
                            {cand.part_number} ({cand.manufacturer || "Unknown Mfg"}) - {cand.package || "Any"}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </Card>

              {/* Pins Definition Table */}
              <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm overflow-hidden">
                <CardHeader className="p-4 border-b border-zinc-800 bg-zinc-900/80">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-emerald-400" />
                        Component Pin Definitions ({componentProfile.pins.length} Pins)
                      </CardTitle>
                      <CardDescription className="text-xs text-zinc-400">
                        Authoritative electrical roles, pin numbers, and pin functions extracted from datasheet
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  {componentProfile.pins.length === 0 ? (
                    <div className="py-8 text-center text-xs text-zinc-500">
                      No pin definitions extracted in component knowledge base.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-zinc-900/90 text-zinc-400 border-b border-zinc-800 font-mono text-[11px]">
                          <tr>
                            <th className="px-4 py-2.5 font-medium">Pin #</th>
                            <th className="px-4 py-2.5 font-medium">Name</th>
                            <th className="px-4 py-2.5 font-medium">Electrical Role</th>
                            <th className="px-4 py-2.5 font-medium">Pin Type</th>
                            <th className="px-4 py-2.5 font-medium">Description</th>
                            <th className="px-4 py-2.5 font-medium">Datasheet Ref</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                          {componentProfile.pins.map((pin) => (
                            <tr key={pin.pin_number} className="hover:bg-zinc-800/30">
                              <td className="px-4 py-2.5 font-mono text-emerald-400 font-semibold">
                                {pin.pin_number}
                              </td>
                              <td className="px-4 py-2.5 font-medium text-zinc-100">{pin.pin_name}</td>
                              <td className="px-4 py-2.5">
                                {pin.electrical_role ? (
                                  <Badge variant="outline" className="text-[10px] font-mono border-zinc-700 bg-zinc-800 text-cyan-300">
                                    {pin.electrical_role}
                                  </Badge>
                                ) : (
                                  <span className="text-zinc-500">—</span>
                                )}
                              </td>
                              <td className="px-4 py-2.5">
                                <span className="font-mono text-[11px] text-zinc-400">{pin.pin_type}</span>
                              </td>
                              <td className="px-4 py-2.5 text-zinc-400">{pin.description || "—"}</td>
                              <td className="px-4 py-2.5 font-mono text-[10px] text-zinc-500">
                                {pin.source_location?.table || pin.source_location?.section || "Pinout Spec"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* STRICT SEPARATION: Operating Limits vs Absolute Maximum Ratings */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 1. Recommended Operating Limits */}
                <Card className="bg-zinc-900/60 border-emerald-500/30 shadow-sm flex flex-col">
                  <CardHeader className="p-4 border-b border-emerald-500/20 bg-emerald-950/20">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <CardTitle className="text-sm font-semibold text-emerald-300">
                          Recommended Operating Limits
                        </CardTitle>
                      </div>
                      <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
                        {componentProfile.operating_ranges.length} Specs
                      </Badge>
                    </div>
                    <CardDescription className="text-xs text-emerald-400/80 mt-1">
                      Continuous operational envelope. Datasheet guarantees electrical characteristics inside this range.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0 flex-1">
                    {componentProfile.operating_ranges.length === 0 ? (
                      <div className="py-8 text-center text-xs text-zinc-500">
                        No recommended operating limits extracted.
                      </div>
                    ) : (
                      <div className="divide-y divide-zinc-800/60 text-xs">
                        {componentProfile.operating_ranges.map((lim, idx) => (
                          <div key={idx} className="p-3.5 hover:bg-zinc-800/30 flex items-start justify-between gap-3">
                            <div>
                              <div className="font-mono font-medium text-zinc-200">{lim.parameter}</div>
                              {lim.conditions && Object.keys(lim.conditions).length > 0 && (
                                <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
                                  Cond: {JSON.stringify(lim.conditions)}
                                </div>
                              )}
                            </div>
                            <div className="text-right shrink-0">
                              <span className="font-mono text-sm font-semibold text-emerald-400">
                                {lim.raw_value}
                              </span>
                              {lim.valid_range && (
                                <div className="text-[10px] font-mono text-zinc-400">
                                  [{lim.valid_range.min ?? "—"} .. {lim.valid_range.max ?? "—"}] {lim.unit || ""}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 2. Absolute Maximum Ratings */}
                <Card className="bg-zinc-900/60 border-rose-500/40 shadow-sm flex flex-col">
                  <CardHeader className="p-4 border-b border-rose-500/20 bg-rose-950/20">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertOctagon className="w-4 h-4 text-rose-400" />
                        <CardTitle className="text-sm font-semibold text-rose-300">
                          Absolute Maximum Ratings (Stress Only)
                        </CardTitle>
                      </div>
                      <Badge variant="outline" className="text-[10px] font-mono border-rose-500/40 text-rose-400 bg-rose-500/10">
                        {componentProfile.absolute_maximums.length} Ratings
                      </Badge>
                    </div>
                    <CardDescription className="text-xs text-rose-400/80 mt-1">
                      Destructive stress limits. Exceeding causes permanent hardware damage. Functional operation not implied.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0 flex-1">
                    {componentProfile.absolute_maximums.length === 0 ? (
                      <div className="py-8 text-center text-xs text-zinc-500">
                        No absolute maximum ratings extracted.
                      </div>
                    ) : (
                      <div className="divide-y divide-zinc-800/60 text-xs">
                        {componentProfile.absolute_maximums.map((abs, idx) => (
                          <div key={idx} className="p-3.5 hover:bg-zinc-800/30 flex items-start justify-between gap-3">
                            <div>
                              <div className="font-mono font-medium text-zinc-200">{abs.parameter}</div>
                              {abs.conditions && Object.keys(abs.conditions).length > 0 && (
                                <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
                                  Cond: {JSON.stringify(abs.conditions)}
                                </div>
                              )}
                            </div>
                            <div className="text-right shrink-0">
                              <span className="font-mono text-sm font-semibold text-rose-400">
                                {abs.raw_value}
                              </span>
                              {abs.normalized_value !== null && abs.normalized_value !== undefined && (
                                <div className="text-[10px] font-mono text-zinc-400">
                                  SI: {abs.normalized_value} {abs.unit || ""}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Electrical & Thermal Characteristics */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Electrical Characteristics */}
                <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm">
                  <CardHeader className="p-4 border-b border-zinc-800 bg-zinc-900/80">
                    <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                      <Zap className="w-4 h-4 text-cyan-400" />
                      Electrical Characteristics
                    </CardTitle>
                    <CardDescription className="text-xs text-zinc-400">
                      Condition-specific electrical parameters (Vref, Iq, Dropout, PSRR)
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    {componentProfile.electrical_characteristics.length === 0 ? (
                      <div className="py-8 text-center text-xs text-zinc-500">
                        No electrical parameters recorded.
                      </div>
                    ) : (
                      <div className="divide-y divide-zinc-800/60 text-xs">
                        {componentProfile.electrical_characteristics.map((el, idx) => (
                          <div key={idx} className="p-3.5 hover:bg-zinc-800/30 flex items-start justify-between gap-3">
                            <div>
                              <div className="font-mono font-medium text-zinc-200">{el.parameter}</div>
                              {el.conditions && Object.keys(el.conditions).length > 0 && (
                                <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
                                  Conditions: {JSON.stringify(el.conditions)}
                                </div>
                              )}
                            </div>
                            <div className="text-right shrink-0 font-mono text-sm font-semibold text-cyan-400">
                              {el.raw_value}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Thermal Characteristics & Unknowns */}
                <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm">
                  <CardHeader className="p-4 border-b border-zinc-800 bg-zinc-900/80">
                    <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                      <Thermometer className="w-4 h-4 text-amber-400" />
                      Thermal Characteristics & Unresolved Unknowns
                    </CardTitle>
                    <CardDescription className="text-xs text-zinc-400">
                      Rth_JA, Tj_max, and explicit uncharacterized datasheet parameters
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    {/* Thermal specs */}
                    <div>
                      <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                        Thermal Ratings
                      </div>
                      {componentProfile.thermal_characteristics.length === 0 ? (
                        <div className="text-xs text-zinc-500 italic">No thermal specifications recorded.</div>
                      ) : (
                        <div className="space-y-2">
                          {componentProfile.thermal_characteristics.map((th, idx) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between p-2 rounded bg-zinc-950/60 border border-zinc-800 text-xs"
                            >
                              <span className="font-mono text-zinc-300">{th.parameter}</span>
                              <span className="font-mono font-semibold text-amber-400">{th.raw_value}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Explicit Unknowns */}
                    <div>
                      <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <HelpCircle className="w-3.5 h-3.5 text-zinc-400" />
                        Explicitly Missing / Unknown Parameters
                      </div>
                      {componentProfile.unknowns.length === 0 ? (
                        <div className="text-xs text-emerald-400/80">
                          All standard required parameters are characterized in knowledge base.
                        </div>
                      ) : (
                        <div className="flex flex-wrap gap-1.5">
                          {componentProfile.unknowns.map((unk, idx) => (
                            <Badge
                              key={idx}
                              variant="outline"
                              className="text-[10px] font-mono border-rose-900/50 text-rose-300 bg-rose-950/30"
                            >
                              UNKNOWN: {unk}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Application Constraints & Reference Designs */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Application Constraints */}
                <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm">
                  <CardHeader className="p-4 border-b border-zinc-800 bg-zinc-900/80">
                    <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                      <Sliders className="w-4 h-4 text-purple-400" />
                      Application Constraints & Rules
                    </CardTitle>
                    <CardDescription className="text-xs text-zinc-400">
                      Decoupling capacitor requirements, minimum ESR limits, and layout rules
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    {componentProfile.application_constraints.length === 0 ? (
                      <div className="py-8 text-center text-xs text-zinc-500">
                        No application constraints extracted.
                      </div>
                    ) : (
                      <div className="divide-y divide-zinc-800/60 text-xs">
                        {componentProfile.application_constraints.map((c, idx) => (
                          <div key={idx} className="p-3.5 hover:bg-zinc-800/30 space-y-1">
                            <div className="flex items-center justify-between">
                              <Badge
                                variant="outline"
                                className="text-[10px] font-mono border-purple-500/40 text-purple-300 bg-purple-500/10"
                              >
                                {c.constraint_type}
                              </Badge>
                              {c.requirement_value && (
                                <span className="font-mono text-zinc-300">{c.requirement_value}</span>
                              )}
                            </div>
                            <p className="text-zinc-300 text-xs mt-1">{c.description}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Reference Designs */}
                <Card className="bg-zinc-900/60 border-zinc-800 shadow-sm">
                  <CardHeader className="p-4 border-b border-zinc-800 bg-zinc-900/80">
                    <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                      <Layers className="w-4 h-4 text-blue-400" />
                      Reference Application Designs
                    </CardTitle>
                    <CardDescription className="text-xs text-zinc-400">
                      Manufacturer recommended typical circuits & external component requirements
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    {componentProfile.reference_designs.length === 0 ? (
                      <div className="py-8 text-center text-xs text-zinc-500">
                        No reference designs attached.
                      </div>
                    ) : (
                      <div className="divide-y divide-zinc-800/60 text-xs">
                        {componentProfile.reference_designs.map((ref, idx) => (
                          <div key={idx} className="p-3.5 hover:bg-zinc-800/30 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-zinc-200">{ref.title}</span>
                              <Badge variant="outline" className="text-[10px] font-mono border-blue-500/40 text-blue-300">
                                {ref.topology}
                              </Badge>
                            </div>
                            {ref.description && <p className="text-zinc-400 text-xs">{ref.description}</p>}
                            {ref.external_components && ref.external_components.length > 0 && (
                              <div className="mt-2 bg-zinc-950 p-2 rounded border border-zinc-800">
                                <span className="text-[10px] font-mono uppercase text-zinc-500 block mb-1">
                                  Required External Components
                                </span>
                                <div className="space-y-1">
                                  {ref.external_components.map((comp: any, cidx: number) => (
                                    <div key={cidx} className="flex justify-between font-mono text-[11px] text-zinc-400">
                                      <span className="text-zinc-300">{comp.ref_des || `COMP_${cidx + 1}`}</span>
                                      <span>{comp.value || "Specified in notes"}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* DETERMINISTIC TOOLS: Interactive Operating Validator & Applicability */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
                {/* 1. Operating Point Validator */}
                <Card className="bg-zinc-900/80 border-zinc-800 shadow-md">
                  <CardHeader className="p-4 border-b border-zinc-800">
                    <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400" />
                      Operating Point Validator (Deterministic Limit Engine)
                    </CardTitle>
                    <CardDescription className="text-xs text-zinc-400">
                      Tests operating point against recommended operating envelope and absolute maximum ceiling
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="text-[11px] font-mono text-zinc-400 block mb-1">Parameter</label>
                        <Input
                          value={valParam}
                          onChange={(e) => setValParam(e.target.value)}
                          placeholder="e.g. input_voltage"
                          className="h-8 text-xs bg-zinc-950 border-zinc-800"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] font-mono text-zinc-400 block mb-1">Value</label>
                        <Input
                          value={valNumber}
                          onChange={(e) => setValNumber(e.target.value)}
                          placeholder="e.g. 5.8"
                          className="h-8 text-xs bg-zinc-950 border-zinc-800"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] font-mono text-zinc-400 block mb-1">Unit</label>
                        <Input
                          value={valUnit}
                          onChange={(e) => setValUnit(e.target.value)}
                          placeholder="e.g. V"
                          className="h-8 text-xs bg-zinc-950 border-zinc-800"
                        />
                      </div>
                    </div>

                    <Button
                      size="sm"
                      onClick={handleValidateOperating}
                      disabled={valLoading}
                      className="w-full h-8 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                    >
                      {valLoading ? "Evaluating..." : "Validate Operating Point"}
                    </Button>

                    {/* Result Banner */}
                    {valResult && (
                      <div
                        className={`p-3 rounded border text-xs space-y-1.5 ${
                          valResult.status === "OPERATING_POINT_VALID"
                            ? "bg-emerald-950/30 border-emerald-800 text-emerald-200"
                            : valResult.status === "OPERATING_LIMIT_EXCEEDED"
                            ? "bg-amber-950/30 border-amber-800 text-amber-200"
                            : valResult.status === "ABSOLUTE_MAXIMUM_EXCEEDED"
                            ? "bg-rose-950/30 border-rose-800 text-rose-200"
                            : "bg-zinc-900 border-zinc-800 text-zinc-300"
                        }`}
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <span>Status: {valResult.status}</span>
                          <span className="font-mono">{valResult.evaluated_value} {valUnit}</span>
                        </div>
                        <p className="text-[11px] opacity-90">{valResult.explanation}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* 2. Applicability Evaluator */}
                <Card className="bg-zinc-900/80 border-zinc-800 shadow-md">
                  <CardHeader className="p-4 border-b border-zinc-800">
                    <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-cyan-400" />
                      Circuit Applicability Evaluator (Zero Synthetic Scoring)
                    </CardTitle>
                    <CardDescription className="text-xs text-zinc-400">
                      Pure categorical evaluation (APPLICABLE / POTENTIALLY / NOT_APPLICABLE / UNKNOWN)
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    <div>
                      <label className="text-[11px] font-mono text-zinc-400 block mb-1">
                        Circuit Operating Context (JSON)
                      </label>
                      <textarea
                        value={appContextJson}
                        onChange={(e) => setAppContextJson(e.target.value)}
                        rows={3}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded p-2 text-xs font-mono text-zinc-300 focus:outline-none focus:border-zinc-700"
                      />
                    </div>

                    <Button
                      size="sm"
                      onClick={handleEvaluateApplicability}
                      disabled={appLoading}
                      className="w-full h-8 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                    >
                      {appLoading ? "Evaluating..." : "Evaluate Applicability"}
                    </Button>

                    {/* Result Banner */}
                    {appResult && (
                      <div
                        className={`p-3 rounded border text-xs space-y-1.5 ${
                          appResult.status === "APPLICABLE"
                            ? "bg-emerald-950/30 border-emerald-800 text-emerald-200"
                            : appResult.status === "POTENTIALLY_APPLICABLE"
                            ? "bg-cyan-950/30 border-cyan-800 text-cyan-200"
                            : appResult.status === "NOT_APPLICABLE"
                            ? "bg-rose-950/30 border-rose-800 text-rose-200"
                            : "bg-amber-950/30 border-amber-800 text-amber-200"
                        }`}
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <span>Applicability: {appResult.status}</span>
                        </div>
                        {appResult.reasons.length > 0 && (
                          <ul className="list-disc list-inside space-y-0.5 text-[11px] opacity-90">
                            {appResult.reasons.map((r, idx) => (
                              <li key={idx}>{r}</li>
                            ))}
                          </ul>
                        )}
                        {appResult.missing_conditions.length > 0 && (
                          <div className="text-[10px] text-zinc-400 font-mono mt-1">
                            Missing conditions: {appResult.missing_conditions.join(", ")}
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
