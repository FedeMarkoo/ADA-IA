package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.*;

public interface LlmClient {
  LlmCompletion complete(LlmRequest request);
}
