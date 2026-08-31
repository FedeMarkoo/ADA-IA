package com.ada.autonomy.infrastructure.in.rest.dto;

import jakarta.validation.constraints.NotBlank;

public record ScheduledTriggerHttpRequest(
    @NotBlank String name,
    @NotBlank String eventType,
    @NotBlank String cronExpression,
    @NotBlank String timezone,
    @NotBlank String prompt,
    @NotBlank String conversationId,
    boolean enabled) {}
