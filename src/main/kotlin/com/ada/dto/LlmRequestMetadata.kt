package com.ada.dto

data class LlmRequestMetadata(
    val correlationId: String,
    val systemPromptVersion: String? = null,
    val filtersApplied: List<String> = emptyList(),
    val memoryIds: List<String> = emptyList(),
)
