package com.ada.model.infrastructure.out.litellm.dto

import com.fasterxml.jackson.annotation.JsonProperty

data class LiteLlmTool(
    val name: String,
    val description: String,
    @JsonProperty("input_schema") val inputSchema: String,
)
