package com.ada.model.infrastructure.out.litellm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
public record LiteLlmTool(String name,String description,@JsonProperty("input_schema") String inputSchema) {}
