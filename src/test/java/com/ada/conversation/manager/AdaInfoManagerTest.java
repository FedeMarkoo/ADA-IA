package com.ada.conversation.manager;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class AdaInfoManagerTest {
  @Test
  void recognizesOnlyInfoCommand() {
    var manager = new AdaInfoManager();

    assertThat(manager.supports(" /i ")).isTrue();
    assertThat(manager.supports("/info")).isFalse();
  }

  @Test
  void describesDeploymentMetadata() {
    var manager = new AdaInfoManager();
    ReflectionTestUtils.setField(manager, "applicationName", "ada");
    ReflectionTestUtils.setField(manager, "deployedVersion", "sha-123");
    ReflectionTestUtils.setField(manager, "commitId", "abc123");
    ReflectionTestUtils.setField(manager, "defaultModel", "ollama/llama3.2:1b");

    assertThat(manager.describe())
        .contains("version=sha-123", "commit=abc123", "model=ollama/llama3.2:1b");
  }
}
