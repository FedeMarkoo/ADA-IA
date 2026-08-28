package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.*;

public interface ToolExecutor {
  boolean supports(String toolName);

  ToolExecutionResult execute(LlmToolCall call);
}
