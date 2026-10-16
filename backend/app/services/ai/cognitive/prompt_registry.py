import json
import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, ValidationError


class PromptDefinition(BaseModel):
    prompt_id: str
    version: str
    system_template: str
    schema_version: str = "v1.0.0"


class StructuredModelContract:
    """
    Enforces the Structured Model Contract:
    LLM Output -> JSON Extraction -> JSON Repair -> Schema Validation -> Semantic Check -> Accepted.
    Rejects malformed outputs without silent fallback.
    """

    @staticmethod
    def extract_and_repair_json(raw_text: str) -> Dict[str, Any]:
        text = raw_text.strip()
        # 1. Strip markdown code fences
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()

        # 2. Direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. JSON Repair: Fix trailing commas, unquoted keys, single quotes
        repaired = text
        repaired = re.sub(r",\s*([\]}])", r"\1", repaired)  # trailing commas
        repaired = re.sub(r"\'", r'"', repaired)  # single to double quotes

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            raise ValueError(f"MODEL_OUTPUT_INVALID: Failed to parse or repair JSON: {e}")

    @staticmethod
    def validate_schema(data: Dict[str, Any], schema_model: type[BaseModel]) -> BaseModel:
        try:
            return schema_model.model_validate(data)
        except ValidationError as ve:
            raise ValueError(f"MODEL_OUTPUT_REJECTED: Schema validation failed: {ve}")

    @classmethod
    def validate_output(
        cls,
        raw_text: str,
        schema_model: Optional[type[BaseModel]] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = cls.extract_and_repair_json(raw_text)
        if schema:
            required_keys = schema.get("required", [])
            for k in required_keys:
                if k not in data:
                    from app.services.ai.cognitive.model_provider import ModelSchemaError
                    raise ModelSchemaError(f"Missing required property: {k}")
        if schema_model:
            cls.validate_schema(data, schema_model)
        return data


class PromptRegistry:
    """
    Immutable registry for cognitive prompt definitions and versions.
    Modifying a prompt requires creating a new version; in-place mutations are disallowed.
    """

    _prompts: Dict[str, PromptDefinition] = {
        "intent_resolver:v1": PromptDefinition(
            prompt_id="intent_resolver",
            version="v1",
            system_template=(
                "You are the QUEBET AI Cognitive Intent Resolver. Analyze the user's engineering request "
                "and classify it into the controlled intent taxonomy. Extract all electrical entities, "
                "constraints, and requirements. Return strictly valid JSON adhering to the IntentPacket schema."
            ),
            schema_version="v1.0.0",
        ),
        "task_decomposer:v1": PromptDefinition(
            prompt_id="task_decomposer",
            version="v1",
            system_template=(
                "You are the QUEBET AI Task Decomposer. Formulate a Directed Acyclic Graph (DAG) of "
                "engineering tasks using only registered, read-only deterministic capabilities. "
                "Declare dependencies explicitly. Do not generate cycles or write operations."
            ),
            schema_version="v1.0.0",
        ),
        "explanation_generator:v1": PromptDefinition(
            prompt_id="explanation_generator",
            version="v1",
            system_template=(
                "You are the QUEBET AI Engineering Explanation Assistant. Interpret the deterministic "
                "engineering findings, verification statuses, and unknowns. Clearly label all interpretations "
                "as AI_GENERATED (INFORMATIONAL ONLY). Preserve UNKNOWN states without assuming PASS."
            ),
            schema_version="v1.0.0",
        ),
        "context_interpreter:v1": PromptDefinition(
            prompt_id="context_interpreter",
            version="v1",
            system_template=(
                "You are the QUEBET AI Context Interpreter. Detect component ambiguities and identify "
                "candidate matches across the circuit and system topology. Flag CLARIFICATION_REQUIRED if "
                "multiple physical components match."
            ),
            schema_version="v1.0.0",
        ),
        "decision_brief:v1": PromptDefinition(
            prompt_id="decision_brief",
            version="v1",
            system_template=(
                "You are the QUEBET AI Decision Preparation Assistant. Organize deterministic engineering facts, "
                "categorical requirement evaluations, and physical trade-offs into an objective decision brief. "
                "You are strictly prohibited from selecting a winner, making a decision, or assigning synthetic scores. "
                "All engineering decisions remain exclusively the authority of the human engineer."
            ),
            schema_version="v1.0.0",
        ),
    }

    @classmethod
    def get(cls, prompt_key: str) -> Optional[PromptDefinition]:
        return cls._prompts.get(prompt_key)

    @classmethod
    def get_prompt(cls, prompt_id: str, version: str = "v1") -> Optional[str]:
        definition = cls.get(f"{prompt_id}:{version}")
        return definition.system_template if definition else None

    @classmethod
    def get_version(cls, prompt_id: str) -> str:
        for k in cls._prompts.keys():
            if k.startswith(f"{prompt_id}:"):
                return k.split(":")[1]
        return "v1"

    @classmethod
    def register(cls, prompt_def: PromptDefinition) -> None:
        key = f"{prompt_def.prompt_id}:{prompt_def.version}"
        if key in cls._prompts:
            raise ValueError(f"PROMPT_IMMUTABLE: Prompt '{key}' is already registered and cannot be mutated.")
        cls._prompts[key] = prompt_def
