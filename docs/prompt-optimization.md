# Prompt optimization

ADA keeps the complete `LlmRequest` in memory and creates an optimized copy only at the provider boundary. The default optimizer is a local, deterministic implementation inspired by Caveman Compression.

It compacts only generated `MEMORIES` and `COMPACTED_PROMPT` system blocks by removing redundant connective phrases, repeated whitespace, and blank lines. User messages, the main system prompt, tool schemas, tool calls, tool responses, JSON, and code are left byte-for-byte unchanged. This prevents token savings from changing protocol data or user intent.

The feature is enabled by default and can be disabled with `ADA_LLM_PROMPT_OPTIMIZATION_ENABLED=false`. `ADA_LLM_PROMPT_OPTIMIZATION_MIN_CHARS` controls the minimum block length; the default is `120` characters.

Metrics do not record prompt contents. `ada_llm_prompt_optimization_total` counts provider calls, while `ada_llm_prompt_optimization_tokens_total{version=original|optimized}` exposes estimated context tokens before and after the copy is optimized.

This is intentionally a first safe layer. Token reduction should be evaluated with provider-reported input tokens and answer-quality checks before expanding compression to tool responses or user content.
