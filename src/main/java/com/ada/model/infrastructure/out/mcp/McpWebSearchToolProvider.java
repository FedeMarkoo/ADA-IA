package com.ada.model.infrastructure.out.mcp;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class McpWebSearchToolProvider implements ToolProvider {
  public List<LlmTool> tools() {
    return List.of(
        new LlmTool(
            "web_search",
            "Search the public internet for current information.",
            "{\"type\":\"object\",\"properties\":{\"query\":{\"type\":\"string\"},\"max_results\":{\"type\":\"integer\"}},\"required\":[\"query\"]}"));
  }
}
