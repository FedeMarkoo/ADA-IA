package com.ada.model.infrastructure.out.litellm.dto;

import java.util.List;

public record LiteLlmResponse(String model, List<LiteLlmChoice> choices, LiteLlmUsage usage) {}
