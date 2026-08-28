package com.ada.observability.api;

public interface OperationScope extends AutoCloseable {
  OperationScope status(int statusCode);

  OperationScope request(Object request);

  OperationScope response(Object response);

  OperationScope event(String name, Object value);

  OperationScope externalCall(ExternalCall call);

  OperationScope failure(Throwable throwable);

  OperationLog snapshot();

  @Override
  void close();
}
