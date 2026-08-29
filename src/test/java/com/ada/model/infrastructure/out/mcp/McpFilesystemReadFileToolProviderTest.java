package com.ada.model.infrastructure.out.mcp;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class McpFilesystemReadFileToolProviderTest {
  @Test
  void publishesBoundedReadOnlyFileContract() {
    var tool = new McpFilesystemReadFileToolProvider().tools().getFirst();
    assertEquals("filesystem.read_file", tool.name());
    assertEquals(
        "{\"type\":\"object\",\"properties\":{\"path\":{\"type\":\"string\"},\"max_bytes\":{\"type\":\"integer\",\"minimum\":1,\"default\":1048576}},\"required\":[\"path\"],\"additionalProperties\":false}",
        tool.inputSchema());
  }
}
