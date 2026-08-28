package com.ada.observability.api;

import java.time.Instant;
import java.util.Map;

public record ExternalCall(
    String target,
    String method,
    Integer statusCode,
    Object request,
    Object response,
    Instant beginTime,
    Instant endTime,
    String exceptionMessage,
    Map<String, String> headers) {}
