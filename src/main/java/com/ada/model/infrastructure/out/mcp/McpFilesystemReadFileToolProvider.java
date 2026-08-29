package com.ada.model.infrastructure.out.mcp;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class McpFilesystemReadFileToolProvider implements ToolProvider {
  public List<LlmTool> tools() {
    return List.of(
        new LlmTool(
            "filesystem.read_file",
            "Read a text file inside ADA's authorized filesystem roots.",
            "{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},\"max_bytes\":{\"type\":\"integer\",\"minimum\":1,\"default\":1048576}},\"required\":[\"path\"],\"additionalProperties\":false}"));
  }
}
