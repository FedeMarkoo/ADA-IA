package com.ada.conversation.manager;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.ada.conversation.application.ToolProvider;
import com.ada.conversation.application.dto.LlmTool;
import java.util.List;
import org.junit.jupiter.api.Test;

class ToolManagerTest {
  @Test
  void rejectsPublishedToolWithoutExecutor() {
    ToolProvider provider =
        () -> List.of(new LlmTool("missing", "Missing executor", "{\"type\":\"object\"}"));
    var manager = new ToolManager(List.of(provider), List.of());

    assertThatThrownBy(manager::validatePublishedTools)
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("missing");
  }
}
