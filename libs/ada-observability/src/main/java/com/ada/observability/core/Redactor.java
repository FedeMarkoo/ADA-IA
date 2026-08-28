package com.ada.observability.core;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.regex.Pattern;

public final class Redactor {
  private static final Pattern KEY =
      Pattern.compile(
          "(?i)(\\\"[^\\\"]*(?:auth|token|clave|pass(?:word)?|api[-_]?key|client_secret)[^\\\"]*\\\"\\s*:\\s*)\\\"(?:\\\\.|[^\\\"])*\\\"");
  private final ObjectMapper mapper;
  private final List<String> hiddenFields;

  public Redactor(ObjectMapper mapper, List<String> hiddenFields) {
    this.mapper = mapper;
    this.hiddenFields = hiddenFields;
  }

  public String json(Object value) {
    try {
      return redact(mapper.writeValueAsString(value));
    } catch (JsonProcessingException e) {
      return "{\"serializationError\":\"" + e.getClass().getSimpleName() + "\"}";
    }
  }

  public String redact(String json) {
    String result = json;
    for (String field : hiddenFields) {
      if (field == null || field.isBlank()) continue;
      result =
          Pattern.compile(
                  "(?i)(\\\""
                      + Pattern.quote(field.trim())
                      + "\\\"\\s*:\\s*)\\\"(?:\\\\.|[^\\\"])*\\\"")
              .matcher(result)
              .replaceAll("$1\\\"hidden\\\"");
    }
    return KEY.matcher(result).replaceAll("$1\\\"hidden\\\"");
  }
}
