package com.ada.observability.api;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@JsonInclude(JsonInclude.Include.NON_NULL)
public final class OperationLog {
  private final String operation;
  private final String kind;
  private final Instant beginTime;
  private Instant endTime;
  private Long duration;
  private TraceContext trace;
  private Integer statusCode;
  private Object request;
  private Object response;
  private Map<String, Object> eventData;
  private final List<ExternalCall> externalCalls = new ArrayList<>();
  private String exceptionMessage;

  public OperationLog(String operation, String kind, TraceContext trace) {
    this.operation = operation; this.kind = kind; this.trace = trace; this.beginTime = Instant.now();
  }
  public void finish() { endTime = Instant.now(); duration = endTime.toEpochMilli() - beginTime.toEpochMilli(); }
  public String getOperation() { return operation; }
  public String getKind() { return kind; }
  public Instant getBeginTime() { return beginTime; }
  public Instant getEndTime() { return endTime; }
  public Long getDuration() { return duration; }
  public TraceContext getTrace() { return trace; }
  public Integer getStatusCode() { return statusCode; }
  public Object getRequest() { return request; }
  public Object getResponse() { return response; }
  public Map<String, Object> getEventData() { return eventData; }
  public List<ExternalCall> getExternalCalls() { return List.copyOf(externalCalls); }
  public String getExceptionMessage() { return exceptionMessage; }
  public void status(Integer value) { statusCode = value; }
  public void request(Object value) { request = value; }
  public void response(Object value) { response = value; }
  public void event(String name, Object value) { if (eventData == null) eventData = new LinkedHashMap<>(); eventData.put(name, value); }
  public void externalCall(ExternalCall value) { externalCalls.add(value); }
  public void failure(Throwable value) { exceptionMessage = value == null ? null : value.toString(); }
}
