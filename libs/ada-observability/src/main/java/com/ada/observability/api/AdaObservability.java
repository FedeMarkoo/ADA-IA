package com.ada.observability.api;

public interface AdaObservability {
  OperationScope start(String operation, String kind);
  OperationScope start(String operation, String kind, TraceContext traceContext);
  TraceContext currentTrace();
  void recordExternalCall(ExternalCall call);
}
