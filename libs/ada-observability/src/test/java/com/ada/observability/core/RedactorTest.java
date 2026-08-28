package com.ada.observability.core;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.junit.jupiter.api.Test;

class RedactorTest {
  @Test
  void redactsConfiguredAndBuiltInFields() {
    Redactor redactor = new Redactor(new ObjectMapper(), List.of("prompt"));
    String json =
        redactor.json(java.util.Map.of("token", "secret", "prompt", "private", "ok", "value"));
    assertThat(json)
        .contains("\"token\":\"hidden\"")
        .contains("\"prompt\":\"hidden\"")
        .contains("\"ok\":\"value\"");
  }
}
