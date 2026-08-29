package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.LlmRequest;

/** Optimizes a request copy immediately before it is sent to an LLM provider. */
public interface PromptOptimizer {
  LlmRequest optimize(LlmRequest request);
}
