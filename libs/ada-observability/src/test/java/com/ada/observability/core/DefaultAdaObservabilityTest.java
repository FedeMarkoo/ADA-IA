package com.ada.observability.core;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.observability.api.OperationLog;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class DefaultAdaObservabilityTest {
  @Test
  void closesOnceAndSendsStructuredEvent() {
    AtomicReference<OperationLog> result = new AtomicReference<>();
    var observability = new DefaultAdaObservability("ada", result::set);
    try (var scope = observability.start("chat", "EVENT")) {
      scope.event("stage", "model").status(200);
    }
    assertThat(result.get().getDuration()).isNotNull();
    assertThat(result.get().getTrace().correlationId()).isNotBlank();
    assertThat(result.get().getEventData()).containsEntry("stage", "model");
  }
}
