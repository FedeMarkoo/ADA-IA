package com.ada;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ada.shared.observability.AdaMetrics;
import com.ada.shared.observability.TokenUsageEstimator;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

class AdaMetricsTest {
  @Test
  void recordsLastRequestDurationAndResetsActiveRequests() {
    var registry = new SimpleMeterRegistry();
    var metrics = new AdaMetrics(registry, new TokenUsageEstimator());
    metrics.registerGauges();

    long started = metrics.startRequest();
    assertEquals(1.0, registry.get("ada_requests_active").gauge().value());
    metrics.finishRequest(started);

    assertEquals(0.0, registry.get("ada_requests_active").gauge().value());
    assertTrue(registry.get("ada_request_last_duration_seconds").gauge().value() >= 0);
  }

  @Test
  void recordsTheLastDurationForEachPipelineStage() {
    var registry = new SimpleMeterRegistry();
    var metrics = new AdaMetrics(registry, new TokenUsageEstimator());
    metrics.registerGauges();

    metrics.measureStage("context_creation", () -> "done");

    assertTrue(
        registry
                .get("ada_pipeline_stage_last_duration_seconds")
                .tag("stage", "context_creation")
                .gauge()
                .value()
            >= 0);
  }
}
