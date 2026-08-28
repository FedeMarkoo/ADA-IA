package com.ada.model.infrastructure.out;

import com.ada.conversation.application.dto.*;
import com.ada.model.application.port.out.ModelSelectionStrategy;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(10)
public class RequestedModelSelectionStrategy implements ModelSelectionStrategy {
  public boolean supports(ChatRequest r) {
    return r.requestedModel() != null && !r.requestedModel().isBlank();
  }

  public ModelSelection select(ChatRequest r) {
    return new ModelSelection(r.requestedModel().trim());
  }
}
