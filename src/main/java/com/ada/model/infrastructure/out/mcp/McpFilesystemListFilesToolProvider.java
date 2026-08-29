package com.ada.model.infrastructure.out.mcp;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class McpFilesystemListFilesToolProvider implements ToolProvider {
  public List<LlmTool> tools() {
    return List.of(
        new LlmTool(
            "filesystem.list_files",
            "List files and directories inside ADA's authorized filesystem roots.",
            "{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},\"recursive\":{\"type\":\"boolean\",\"default\":false}},\"required\":[\"path\"],\"additionalProperties\":false}"));
  }
}
