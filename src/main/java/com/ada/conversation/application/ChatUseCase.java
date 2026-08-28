package com.ada.conversation.application;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.in.RequestFilter;
import com.ada.conversation.application.port.out.*;
import com.ada.conversation.manager.AdaInfoManager;
import com.ada.conversation.manager.MemoryManager;
import com.ada.conversation.manager.ToolManager;
import com.ada.observability.api.AdaObservability;
import com.ada.shared.observability.AdaMetrics;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.annotation.AnnotationAwareOrderComparator;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class ChatUseCase {
  private final SelectModelUseCase selector;
  private final LlmRequestFactory factory;
  private final LlmClient client;
  private final AdaMetrics metrics;
  private final AdaObservability observability;
  private final List<RequestFilter> filters;
  private final ToolManager toolManager;
  private final MemoryManager memoryManager;
  private final AdaInfoManager adaInfoManager;
  private final MessageStateTracker tracker;
  private final MessageResultStore results;

  @Qualifier("conversationExecutor") private final Executor executor;

  public ChatResult execute(ChatRequest input) {
    String id = UUID.randomUUID().toString();
    return execute(id, input);
  }

  public String start(ChatRequest input) {
    String id = UUID.randomUUID().toString();
    tracker.update(id, new MessageExecutionState.Received());
    CompletableFuture.runAsync(() -> execute(id, input), executor);
    return id;
  }

  private ChatResult execute(String id, ChatRequest input) {
    long startedAtNanos = metrics.startRequest();
    var tokenUsage = new ArrayList<TokenUsageComponent>();
    try (var operation = observability.start("conversation.chat", "EVENT")) {
      operation.event("messageId", id).event("inputType", input.getClass().getSimpleName());
      try {
        tracker.update(id, new MessageExecutionState.FilteringCommand());
        var r = metrics.measureStage("filtering_command", () -> applyFilters(input));
        if (adaInfoManager.supports(r.message())) {
          operation.event("outcome", "success");
          return executeInfoCommand(id);
        }
        var selection = selector.execute(r);
        tracker.update(id, new MessageExecutionState.SelectingContext());
        tracker.update(id, new MessageExecutionState.CreatingContext());
        var req =
            metrics.measureStage("context_creation", () -> factory.create(r, selection.model()));
        var completion = invoke(id, req, tokenUsage);
        int rounds = 0;
        while (!completion.toolCalls().isEmpty()) {
          if (rounds++ >= 8) throw new IllegalStateException("Maximum tool rounds exceeded");
          var messages = new ArrayList<>(req.messages());
          messages.add(
              new LlmMessage(
                  LlmMessageRole.ASSISTANT,
                  completion.content(),
                  LlmContentComponent.RESPONSE,
                  completion.toolCalls()));
          for (var call : completion.toolCalls()) {
            tracker.update(id, new MessageExecutionState.InvokingTool(call.name()));
            var result = metrics.measureStage("tool_invoke", () -> toolManager.execute(call));
            messages.add(
                new LlmMessage(
                    LlmMessageRole.TOOL,
                    result.content(),
                    LlmContentComponent.TOOL_RESPONSE,
                    List.of(),
                    result.toolCallId()));
          }
          req =
              new LlmRequest(
                  req.model(),
                  messages,
                  req.tools(),
                  req.temperature(),
                  req.maxTokens(),
                  req.metadata());
          completion = invoke(id, req, tokenUsage);
        }
        metrics.recordRequest("conversation", "chat", "success");
        var result =
            new ChatResult(
                id,
                completion.content(),
                completion.model(),
                completion.inputTokens(),
                completion.outputTokens(),
                aggregateTokenUsage(tokenUsage));
        memoryManager.review(r, result.content());
        results.save(result);
        tracker.update(id, new MessageExecutionState.Completed());
        operation.event("outcome", "success");
        return result;
      } catch (RuntimeException e) {
        operation.event("outcome", "failure").failure(e);
        tracker.update(
            id,
            new MessageExecutionState.Failed(
                e.getMessage() == null ? "unknown error" : e.getMessage()));
        throw e;
      } finally {
        metrics.finishRequest(startedAtNanos);
      }
    }
  }

  private ChatResult executeInfoCommand(String id) {
    tracker.update(id, new MessageExecutionState.Completed());
    metrics.recordRequest("command", "info", "success");
    var result = new ChatResult(id, adaInfoManager.describe(), "command", null, null, List.of());
    results.save(result);
    return result;
  }

  private ChatRequest applyFilters(ChatRequest input) {
    var result = input;
    var orderedFilters = new ArrayList<>(filters);
    orderedFilters.sort(AnnotationAwareOrderComparator.INSTANCE);
    for (var filter : orderedFilters) if (filter.supports(result)) result = filter.apply(result);
    return result;
  }

  private LlmCompletion invoke(String id, LlmRequest r, List<TokenUsageComponent> tokenUsage) {
    tracker.update(id, new MessageExecutionState.InvokingModel(r.model()));
    var c =
        metrics.measureStage(
            "model_invoke", () -> metrics.measureLlm(r.model(), () -> client.complete(r)));
    tokenUsage.addAll(metrics.recordTokenBreakdown(r, c));
    return c;
  }

  private List<TokenUsageComponent> aggregateTokenUsage(List<TokenUsageComponent> usage) {
    var totals = new LinkedHashMap<String, Long>();
    var sources = new LinkedHashMap<String, TokenUsageSource>();
    usage.forEach(
        item -> {
          totals.merge(item.component(), item.tokens(), Long::sum);
          sources.put(item.component(), item.source());
        });
    return totals.entrySet().stream()
        .map(
            item ->
                new TokenUsageComponent(item.getKey(), item.getValue(), sources.get(item.getKey())))
        .toList();
  }
}
