# Prompt Versioning & Structured Model Contract

## 1. Prompt Immutability
All prompts used by the Cognitive Engineering Layer are registered in `PromptRegistry` with immutable version identifiers:
- `intent_resolver:v1`
- `task_decomposer:v1`
- `explanation_generator:v1`
- `context_interpreter:v1`

Attempting to mutate an existing prompt key raises `PROMPT_IMMUTABLE`. Upgrades require registering a new version key (e.g. `intent_resolver:v2`).

## 2. Structured Model Contract
All model outputs must satisfy the sequential contract:
```text
LLM Response
    ↓
JSON Extraction (fences stripped)
    ↓
JSON Repair (trailing commas, quotes)
    ↓
Schema Validation (required keys verified)
    ↓
Semantic Check (valid taxonomy types)
    ↓
Accepted Output
```

If parsing or repair fails, `MODEL_OUTPUT_INVALID` is raised. If schema properties are missing, `MODEL_SCHEMA_FAILURE` is raised. Silent fallbacks or hallucinations are prohibited.
