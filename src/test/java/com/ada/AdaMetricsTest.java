package com.ada;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ada.conversation.application.dto.LlmCompletion;
import com.ada.conversation.application.dto.LlmContentComponent;
import com.ada.conversation.application.dto.LlmMessage;
import com.ada.conversation.application.dto.LlmMessageRole;
import com.ada.conversation.application.dto.LlmRequest;
import com.ada.conversation.application.dto.LlmRequestMetadata;
import com.ada.shared.observability.AdaMetrics;
import com.ada.shared.observability.TokenUsageEstimator;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.List;
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

  @Test
  void recordsMcpSuccessAndFailureWithDuration() {
    var registry = new SimpleMeterRegistry();
    var metrics = new AdaMetrics(registry, new TokenUsageEstimator());
    metrics.measureMcp("web_search", () -> "ok");
    try {
      metrics.measureMcp(
          "web_search",
          () -> {
            throw new IllegalStateException("failure");
          });
    } catch (IllegalStateException ignored) {
      // The operation error must remain visible to the caller.
    }

    assertEquals(
        1.0,
        registry
            .get("ada_mcp_calls_total")
            .tag("tool", "web_search")
            .tag("outcome", "success")
            .counter()
            .count());
    assertEquals(
        1.0,
        registry
            .get("ada_mcp_calls_total")
            .tag("tool", "web_search")
            .tag("outcome", "failure")
            .counter()
            .count());
    assertTrue(registry.get("ada_mcp_duration_seconds").timer().count() == 2);
  }

  @Test
  void recordsLastContextTokensPerModel() {
    var registry = new SimpleMeterRegistry();
    var metrics = new AdaMetrics(registry, new TokenUsageEstimator());
    var request =
        new LlmRequest(
            "ollama/test",
            List.of(
                new LlmMessage(LlmMessageRole.SYSTEM, "system", LlmContentComponent.SYSTEM),
                new LlmMessage(LlmMessageRole.USER, "prompt", LlmContentComponent.PROMPT)),
            List.of(),
            new LlmRequestMetadata("id"));

    metrics.recordTokenBreakdown(request, new LlmCompletion("answer", "ollama/test", 2L, 1L));

    assertTrue(
        registry.get("ada_llm_context_tokens_last").tag("model", "ollama/test").gauge().value()
            > 0);
  }
}
