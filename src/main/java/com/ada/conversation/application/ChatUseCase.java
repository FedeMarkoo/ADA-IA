package com.ada.conversation.application;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.in.RequestFilter;
import com.ada.conversation.application.port.out.*;
import com.ada.shared.observability.AdaMetrics;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import org.springframework.core.annotation.AnnotationAwareOrderComparator;
import org.springframework.stereotype.Service;

@Service
public class ChatUseCase {
  private final SelectModelUseCase selector;
  private final LlmRequestFactory factory;
  private final LlmClient client;
  private final AdaMetrics metrics;
  private final List<RequestFilter> filters;
  private final List<ToolExecutor> tools;
  private final MessageStateTracker tracker;
  private final Executor executor;

  public ChatUseCase(
      SelectModelUseCase s,
      LlmRequestFactory f,
      LlmClient c,
      AdaMetrics m,
      List<RequestFilter> filters,
      List<ToolExecutor> tools,
      MessageStateTracker t,
      Executor executor) {
    selector = s;
    factory = f;
    client = c;
    metrics = m;
    this.filters = filters;
    this.tools = tools;
    tracker = t;
    this.executor = executor;
  }

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
    try {
      tracker.update(id, new MessageExecutionState.FilteringCommand());
      var r = input;
      var fs = new ArrayList<>(filters);
      fs.sort(AnnotationAwareOrderComparator.INSTANCE);
      for (var f : fs) if (f.supports(r)) r = f.apply(r);
      var selection = selector.execute(r);
      tracker.update(id, new MessageExecutionState.CreatingContext());
      var req = factory.create(r, selection.model());
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
          var result = executor.execute(call);
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
      return new ChatResult(
          id,
          completion.content(),
          completion.model(),
          completion.inputTokens(),
          completion.outputTokens());
    } catch (RuntimeException e) {
      tracker.update(
          id,
          new MessageExecutionState.Failed(
              e.getMessage() == null ? "unknown error" : e.getMessage()));
      throw e;
    }
  }

  private LlmCompletion invoke(String id, LlmRequest r) {
    tracker.update(id, new MessageExecutionState.InvokingModel(r.model()));
    var c = metrics.measureLlm(r.model(), () -> client.complete(r));
    metrics.recordTokenBreakdown(r, c);
    return c;
  }
}
