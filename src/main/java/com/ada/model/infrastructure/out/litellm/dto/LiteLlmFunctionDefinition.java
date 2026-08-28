package com.ada.model.infrastructure.out.litellm.dto;

import com.fasterxml.jackson.databind.JsonNode;

public record LiteLlmFunctionDefinition(String name, String description, JsonNode parameters) {}
