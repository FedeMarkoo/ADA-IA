package com.ada.conversation.infrastructure.out.prompt;

import com.ada.conversation.application.SystemPromptProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class SqliteSystemPromptProvider implements SystemPromptProvider {
  private final JdbcTemplate jdbc;

  public SqliteSystemPromptProvider(JdbcTemplate j) {
    jdbc = j;
  }

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
