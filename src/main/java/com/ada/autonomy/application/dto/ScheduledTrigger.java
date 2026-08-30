package com.ada.autonomy.application.dto;

import java.time.Instant;

public record ScheduledTrigger(
    long id,
    String name,
    String eventType,
    String cronExpression,
    String timezone,
    String prompt,
    String conversationId,
    boolean enabled,
    Instant nextRunAt,
    Instant lastRunAt) {}
