package com.ada.conversation.application;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.in.RequestFilter;
import com.ada.conversation.application.port.out.*;
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
  private final List<RequestFilter> filters;
  private final List<ToolExecutor> tools;
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
    try {
      tracker.update(id, new MessageExecutionState.FilteringCommand());
      var r = metrics.measureStage("filtering_command", () -> applyFilters(input));
      var selection = selector.execute(r);
      tracker.update(id, new MessageExecutionState.CreatingContext());
      var req =
          metrics.measureStage("context_creation", () -> factory.create(r, selection.model()));
      var completion = invoke(id, req);
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
          var executor =
              tools.stream()
                  .filter(x -> x.supports(call.name()))
                  .findFirst()
                  .orElseThrow(
                      () ->
                          new IllegalStateException(
                              "No executor available for tool '" + call.name() + "'"));
          var result = metrics.measureStage("tool_invoke", () -> executor.execute(call));
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
        completion = invoke(id, req);
      }
      tracker.update(id, new MessageExecutionState.Completed());
      metrics.recordRequest("conversation", "chat", "success");
      var result =
          new ChatResult(
              id,
              completion.content(),
              completion.model(),
              completion.inputTokens(),
              completion.outputTokens());
      results.save(result);
      return result;
    } catch (RuntimeException e) {
      tracker.update(
          id,
          new MessageExecutionState.Failed(
              e.getMessage() == null ? "unknown error" : e.getMessage()));
      throw e;
    } finally {
      metrics.finishRequest(startedAtNanos);
    }
  }

  private ChatRequest applyFilters(ChatRequest input) {
    var result = input;
    var orderedFilters = new ArrayList<>(filters);
    orderedFilters.sort(AnnotationAwareOrderComparator.INSTANCE);
    for (var filter : orderedFilters) if (filter.supports(result)) result = filter.apply(result);
    return result;
  }

  private LlmCompletion invoke(String id, LlmRequest r) {
    tracker.update(id, new MessageExecutionState.InvokingModel(r.model()));
    var c =
        metrics.measureStage(
            "model_invoke", () -> metrics.measureLlm(r.model(), () -> client.complete(r)));
    metrics.recordTokenBreakdown(r, c);
    return c;
  }
}
