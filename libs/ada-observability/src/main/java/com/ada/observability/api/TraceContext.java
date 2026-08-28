package com.ada.observability.api;

import java.util.UUID;

public record TraceContext(String correlationId, String caller, String initialCaller) {
  public static TraceContext create(
      String applicationName, String correlationId, String caller, String initialCaller) {
    String id =
        correlationId == null || correlationId.isBlank()
            ? UUID.randomUUID().toString()
            : correlationId;
    String current = caller == null || caller.isBlank() ? applicationName : caller;
    String origin = initialCaller == null || initialCaller.isBlank() ? current : initialCaller;
    return new TraceContext(id, current, origin);
  }
}
