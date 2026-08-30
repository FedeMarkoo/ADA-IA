package com.ada.model.infrastructure.out.mcp;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class McpCalendarToolProvider implements ToolProvider {
  public List<LlmTool> tools() {
    return List.of(
        new LlmTool(
            "calendar_upcoming_events",
            "List upcoming events from the primary Google Calendar; use for agenda, appointments or commitments.",
            "{\"type\":\"object\",\"properties\":{\"days\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":31},\"max_results\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":20}},\"additionalProperties\":false}"));
  }
}
