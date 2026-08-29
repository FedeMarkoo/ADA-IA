package com.ada.model.infrastructure.out.mcp;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class McpFilesystemListFilesToolProviderTest {
  @Test
  void publishesReadOnlyFilesystemListContract() {
    var tool = new McpFilesystemListFilesToolProvider().tools().getFirst();
    assertEquals("filesystem.list_files", tool.name());
    assertEquals("{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},\"recursive\":{\"type\":\"boolean\",\"default\":false}},\"required\":[\"path\"],\"additionalProperties\":false}", tool.inputSchema());
  }
}
