package com.ada.observability.core;

import com.ada.observability.api.*;
import java.util.Objects;
import java.util.function.Consumer;

public final class DefaultAdaObservability implements AdaObservability {
  private final ThreadLocal<TraceContext> trace = new ThreadLocal<>();
  private final ThreadLocal<OperationLog> activeOperation = new ThreadLocal<>();
  private final String applicationName;
  private final Consumer<OperationLog> sink;

  public DefaultAdaObservability(String applicationName, Consumer<OperationLog> sink) {
    this.applicationName = Objects.requireNonNullElse(applicationName, "unknown");
    this.sink = sink;
  }

  @Override
  public OperationScope start(String operation, String kind) {
    TraceContext context = trace.get();
    if (context == null)
      context = TraceContext.create(applicationName, null, applicationName, applicationName);
    return start(operation, kind, context);
  }

  @Override
  public OperationScope start(String operation, String kind, TraceContext context) {
    OperationLog log = new OperationLog(operation, kind, context);
    boolean root = activeOperation.get() == null;
    if (root) activeOperation.set(log);
    return new OperationScope() {
      private boolean closed;

      public OperationScope status(int value) {
        log.status(value);
        return this;
      }

      public OperationScope request(Object value) {
        log.request(value);
        return this;
      }

      public OperationScope response(Object value) {
        log.response(value);
        return this;
      }

      public OperationScope event(String name, Object value) {
        log.event(name, value);
        return this;
      }

      public OperationScope externalCall(ExternalCall value) {
        log.externalCall(value);
        return this;
      }

      public OperationScope failure(Throwable value) {
        log.failure(value);
        return this;
      }

      public OperationLog snapshot() {
        return log;
      }

      public void close() {
        if (!closed) {
          closed = true;
          log.finish();
          if (root) {
            sink.accept(log);
            activeOperation.remove();
            trace.remove();
          }
        }
      }
    };
  }

  @Override
  public TraceContext currentTrace() {
    return trace.get();
  }

  public void setTrace(TraceContext context) {
    trace.set(context);
  }

  @Override
  public void recordExternalCall(ExternalCall call) {
    OperationLog current = activeOperation.get();
    if (current != null) current.externalCall(call);
  }
}
