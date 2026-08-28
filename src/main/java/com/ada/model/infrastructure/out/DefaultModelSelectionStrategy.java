package com.ada.model.infrastructure.out;

import com.ada.conversation.application.dto.*;
import com.ada.model.application.port.out.ModelSelectionStrategy;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(100)
@NoArgsConstructor
public class DefaultModelSelectionStrategy implements ModelSelectionStrategy {
  @Value("${ada.llm.default-model:openai/gpt-4o-mini}")
  private String model;

  public boolean supports(ChatRequest r) {
    return r.requestedModel() == null;
  }

  public ModelSelection select(ChatRequest r) {
    return new ModelSelection(model);
  }
}
