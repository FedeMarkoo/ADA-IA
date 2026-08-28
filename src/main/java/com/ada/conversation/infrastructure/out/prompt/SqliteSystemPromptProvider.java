package com.ada.conversation.infrastructure.out.prompt;

import com.ada.conversation.application.SystemPromptProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class SqliteSystemPromptProvider implements SystemPromptProvider {
  private final JdbcTemplate jdbc;

  public String content() {
    var r =
        jdbc.query(
            "SELECT content FROM system_prompts WHERE active = 1 ORDER BY version DESC LIMIT 1",
            (rs, n) -> rs.getString("content"));
    if (r.isEmpty())
      throw new IllegalStateException("No active system prompt configured in SQLite");
    return r.getFirst();
  }
}
