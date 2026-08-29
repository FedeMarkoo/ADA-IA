package com.ada.conversation.infrastructure.in.rest.dto;

import jakarta.validation.constraints.NotBlank;

public record RagDocumentHttpRequest(
    @NotBlank String conversationId, @NotBlank String source, @NotBlank String content) {}
