package com.ada.conversation.infrastructure.in.rest.dto;

import jakarta.validation.constraints.NotBlank;

public record ChatHttpRequest(
    @NotBlank String message, String requestedModel, String conversationId) {}
