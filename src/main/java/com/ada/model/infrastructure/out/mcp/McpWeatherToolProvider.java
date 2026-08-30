package com.ada.model.infrastructure.out.mcp;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class McpWeatherToolProvider implements ToolProvider {
  public List<LlmTool> tools() {
    return List.of(
        new LlmTool(
            "weather_current",
            "Current weather. Call for weather, temperature or rain; omit location to use approximate location.",
            "{\"type\":\"object\",\"properties\":{\"location\":{\"type\":\"string\",\"description\":\"City or place; optional.\"}},\"additionalProperties\":false}"));
  }
}
