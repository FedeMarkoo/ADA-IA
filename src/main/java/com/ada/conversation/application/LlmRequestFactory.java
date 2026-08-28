package com.ada.conversation.application;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.manager.ContextManager;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class LlmRequestFactory {
  private final ContextManager assembler;

  public LlmRequest create(ChatRequest r, String model) {
    var c = assembler.build(r);
    return new LlmRequest(
        model,
        c.messages(),
        c.tools(),
        0.2,
        1024,
        new LlmRequestMetadata(UUID.randomUUID().toString()));
  }
}
