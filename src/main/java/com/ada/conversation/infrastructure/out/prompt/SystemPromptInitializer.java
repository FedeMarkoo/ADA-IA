package com.ada.conversation.infrastructure.out.prompt;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class SystemPromptInitializer {
  private static final String DEFAULT_PROMPT_RESOURCE = "default-system-prompt.txt";
  private final JdbcTemplate jdbc;

  public void initialize() {
    if (jdbc.queryForObject("SELECT COUNT(*) FROM system_prompts", Integer.class) > 0) return;
    jdbc.update(
        "INSERT INTO system_prompts(version, content, active) VALUES (?, ?, ?)",
        1,
        readDefaultPrompt(),
        1);
  }

  private String readDefaultPrompt() {
    try {
      return new ClassPathResource(DEFAULT_PROMPT_RESOURCE)
          .getContentAsString(StandardCharsets.UTF_8)
          .trim();
    } catch (IOException exception) {
      throw new IllegalStateException("Default system prompt resource is unavailable", exception);
    }
  }
}
