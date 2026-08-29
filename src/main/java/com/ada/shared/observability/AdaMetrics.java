package com.ada.shared.observability;

import com.ada.conversation.application.dto.*;
import io.micrometer.core.instrument.*;
import jakarta.annotation.PostConstruct;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Supplier;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class AdaMetrics {
  private final MeterRegistry registry;
  private final TokenUsageEstimator estimator;
  private final AtomicInteger activeRequests = new AtomicInteger();
  private final AtomicLong lastRequestDurationNanos = new AtomicLong();
  private final AtomicLong lastRequestCompletedAtMillis = new AtomicLong();
  private final Map<String, AtomicLong> lastStageDurationsNanos = new ConcurrentHashMap<>();
  private final Map<String, AtomicLong> lastContextTokens = new ConcurrentHashMap<>();

  @PostConstruct
  public void registerGauges() {
    registry.gauge("ada_requests_active", activeRequests);
    registry.gauge(
        "ada_request_last_duration_seconds",
        lastRequestDurationNanos,
        value -> Duration.ofNanos(value.get()).toNanos() / 1_000_000_000.0);
    registry.gauge(
        "ada_request_last_completed_at_epoch_seconds",
        lastRequestCompletedAtMillis,
        value -> value.get() / 1_000.0);
  }

  public long startRequest() {
    activeRequests.incrementAndGet();
    registry.counter("ada_requests_started_total").increment();
    return System.nanoTime();
  }

  public void finishRequest(long startedAtNanos) {
    long elapsed = System.nanoTime() - startedAtNanos;
    activeRequests.decrementAndGet();
    lastRequestDurationNanos.set(elapsed);
    lastRequestCompletedAtMillis.set(Instant.now().toEpochMilli());
    Timer.builder("ada_request_duration_seconds")
        .register(registry)
        .record(Duration.ofNanos(elapsed));
  }

  public void recordRequest(String c, String u, String o) {
    registry.counter("ada_requests_total", "context", c, "use_case", u, "outcome", o).increment();
  }

  public java.util.List<TokenUsageComponent> recordTokenBreakdown(LlmRequest r, LlmCompletion c) {
    var components = new java.util.ArrayList<>(estimator.components(r));
    components.removeIf(x -> x.component().equals("total"));
    var contextTokens = components.stream().mapToLong(TokenUsageComponent::tokens).sum();
    var contextGauge =
        lastContextTokens.computeIfAbsent(
            r.model(),
            model ->
                registry.gauge(
                    "ada_llm_context_tokens_last",
                    Tags.of("model", model),
                    new AtomicLong(),
                    value -> value.get()));
    contextGauge.set(contextTokens);
    components.stream()
        .filter(x -> !x.component().equals("total"))
        .forEach(
            x ->
                registry
                    .counter(
                        "ada_llm_tokens_total",
                        "model",
                        r.model(),
                        "component",
                        x.component(),
                        "source",
                        x.source().name().toLowerCase())
                    .increment(x.tokens()));
    if (c.outputTokens() != null) {
      components.add(
          new TokenUsageComponent("response", c.outputTokens(), TokenUsageSource.PROVIDER));
      registry
          .counter(
              "ada_llm_tokens_total",
              "model",
              r.model(),
              "component",
              "response",
              "source",
              "provider")
          .increment(c.outputTokens());
    }
    return components;
  }

  public void recordProviderTokens(String m, Long i, Long o) {
    if (i != null)
      registry
          .counter("ada_llm_provider_tokens_total", "model", m, "direction", "input")
          .increment(i);
    if (o != null)
      registry
          .counter("ada_llm_provider_tokens_total", "model", m, "direction", "output")
          .increment(o);
  }

  public void recordPromptOptimization(LlmRequest original, LlmRequest optimized) {
    long originalTokens = estimatedContextTokens(original);
    long optimizedTokens = estimatedContextTokens(optimized);
    registry.counter("ada_llm_prompt_optimization_total", "model", original.model()).increment();
    registry
        .counter(
            "ada_llm_prompt_optimization_tokens_total",
            "model",
            original.model(),
            "version",
            "original")
        .increment(originalTokens);
    registry
        .counter(
            "ada_llm_prompt_optimization_tokens_total",
            "model",
            original.model(),
            "version",
            "optimized")
        .increment(optimizedTokens);
  }

  private long estimatedContextTokens(LlmRequest request) {
    return estimator.components(request).stream()
        .filter(item -> !item.component().equals("total"))
        .mapToLong(TokenUsageComponent::tokens)
        .sum();
  }

  public <T> T measureLlm(String m, java.util.function.Supplier<T> op) {
    var s = Timer.start(registry);
    try {
      return op.get();
    } finally {
      s.stop(registry.timer("ada_llm_duration_seconds", "model", m));
    }
  }

  public <T> T measureMcp(String tool, java.util.function.Supplier<T> operation) {
    var timer = Timer.start(registry);
    try {
      var result = operation.get();
      registry.counter("ada_mcp_calls_total", "tool", tool, "outcome", "success").increment();
      return result;
    } catch (RuntimeException error) {
      registry.counter("ada_mcp_calls_total", "tool", tool, "outcome", "failure").increment();
      throw error;
    } finally {
      timer.stop(registry.timer("ada_mcp_duration_seconds", "tool", tool));
    }
  }

  public <T> T measureStage(String stage, Supplier<T> operation) {
    AtomicLong lastDuration =
        lastStageDurationsNanos.computeIfAbsent(
            stage,
            key -> {
              AtomicLong value = new AtomicLong();
              registry.gauge(
                  "ada_pipeline_stage_last_duration_seconds",
                  Tags.of("stage", key),
                  value,
                  item -> Duration.ofNanos(item.get()).toNanos() / 1_000_000_000.0);
              return value;
            });
    Timer.Sample sample = Timer.start(registry);
    long startedAtNanos = System.nanoTime();
    try {
      return operation.get();
    } finally {
      lastDuration.set(System.nanoTime() - startedAtNanos);
      sample.stop(
          Timer.builder("ada_pipeline_stage_duration_seconds")
              .tag("stage", stage)
              .register(registry));
    }
  }

  public void recordStageOutcome(String stage, String outcome) {
    registry
        .counter("ada_pipeline_stage_outcomes_total", "stage", stage, "outcome", outcome)
        .increment();
  }

  public void recordContextSelection(String model, ContextSelection selection) {
    registry
        .counter("ada_context_selection_total", "model", model, "outcome", "success")
        .increment();
    selection.mcps().forEach(mcp -> recordSelectedContext("mcp", mcp));
    selection.tools().forEach(tool -> recordSelectedContext("tool", tool));
    selection.memories().forEach(memory -> recordSelectedContext("memory", memory));
  }

  private void recordSelectedContext(String type, String name) {
    registry.counter("ada_context_selection_items_total", "type", type, "item", name).increment();
  }
}
