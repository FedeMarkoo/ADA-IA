package com.ada.conversation.application;

import com.ada.conversation.application.dto.LlmTool;
import java.util.List;

public interface ToolProvider {
  List<LlmTool> tools();
}
