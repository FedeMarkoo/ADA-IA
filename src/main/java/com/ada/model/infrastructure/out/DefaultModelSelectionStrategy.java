package com.ada.model.infrastructure.out;

import com.ada.conversation.application.dto.*;
import com.ada.model.application.port.out.ModelSelectionStrategy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(100)
public class DefaultModelSelectionStrategy implements ModelSelectionStrategy {
  private final String model;

  public DefaultModelSelectionStrategy(
      @Value("${ada.llm.default-model:openai/gpt-4o-mini}") String m) {
    model = m;
  }

  public boolean supports(ChatRequest r) {
    return r.requestedModel() == null;
  }

  public ModelSelection select(ChatRequest r) {
    return new ModelSelection(model);
  }
}
