package com.ada.conversation.manager;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.dto.ToolExecutionResult;
import com.ada.conversation.application.port.out.ToolExecutor;
import jakarta.annotation.PostConstruct;
import java.util.ArrayList;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ToolManager {
  private final List<ToolProvider> providers;
  private final List<ToolExecutor> executors;

  @PostConstruct
  void validatePublishedTools() {
    providers.stream()
        .flatMap(provider -> provider.tools().stream())
        .filter(tool -> executors.stream().noneMatch(executor -> executor.supports(tool.name())))
        .findFirst()
        .ifPresent(
            tool -> {
              throw new IllegalStateException(
                  "No executor available for published tool '" + tool.name() + "'");
            });
  }

  public List<LlmTool> availableTools() {
    var tools = new ArrayList<LlmTool>();
    providers.forEach(provider -> tools.addAll(provider.tools()));
    return List.copyOf(tools);
  }

  public ToolExecutionResult execute(LlmToolCall call) {
    return executors.stream()
        .filter(executor -> executor.supports(call.name()))
        .findFirst()
        .orElseThrow(
            () -> new IllegalStateException("No executor available for tool '" + call.name() + "'"))
        .execute(call);
  }
}
