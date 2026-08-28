package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import com.ada.shared.observability.*;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(60)
@MeasuredContextItem("compacted_prompt")
@RequiredArgsConstructor
public class CompactedPromptContextItem implements ContextItem {
  private final TokenUsageEstimator estimator;

  @Value("${ada.context.max-tokens:12000}")
  private long max;

  public LlmContentComponent component() {
    return LlmContentComponent.COMPACTED_PROMPT;
  }

  public ContextState apply(ChatRequest r, ContextState c) {
    if (estimator.estimate(c) <= max) return c;
    var keep =
        c.messages().stream().filter(m -> m.component() == LlmContentComponent.SYSTEM).toList();
    var summary =
        c.messages().stream()
            .filter(m -> m.component() != LlmContentComponent.SYSTEM)
            .map(m -> m.role().wireName() + ": " + m.content())
            .collect(java.util.stream.Collectors.joining("\n"));
    var all = new java.util.ArrayList<>(keep);
    all.add(
        new LlmMessage(
            LlmMessageRole.SYSTEM, "Previous context summary:\n" + summary, component()));
    return new ContextState(all, c.tools());
  }
}
