package com.ada.conversation.infrastructure.out.prompt;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.DataSourceConfiguration;
import com.ada.shared.infrastructure.dto.LlmProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.jdbc.core.JdbcTemplate;

class SqliteSystemPromptProviderTest {
  @TempDir Path tempDir;

  @Test
  void dataInitializationProvidesPromptWithoutReplacingConfiguredPrompt() throws Exception {
    DataSource dataSource = dataSource();
    executeResource(dataSource, "/schema.sql");
    new SystemPromptInitializer(new JdbcTemplate(dataSource)).initialize();

    JdbcTemplate jdbc = new JdbcTemplate(dataSource);
    jdbc.update(
        "INSERT INTO system_prompts(version, content, active) VALUES (?, ?, ?)",
        2,
        "prompt personalizado",
        1);
    new SystemPromptInitializer(jdbc).initialize();

    assertThat(new SqliteSystemPromptProvider(jdbc).content()).isEqualTo("prompt personalizado");
  }

  private DataSource dataSource() throws Exception {
    var properties = new AdaProperties();
    properties.setDataDir(tempDir.resolve("data").toString());
    properties.setLlm(new LlmProperties("http://localhost", "", "model"));
    return new DataSourceConfiguration().dataSource(properties);
  }

  private void executeResource(DataSource dataSource, String resource) throws Exception {
    String script = Files.readString(Path.of(getClass().getResource(resource).toURI()));
    try (Connection connection = dataSource.getConnection()) {
      for (String statement : script.split(";;")) {
        if (!statement.isBlank()) connection.createStatement().execute(statement);
      }
    }
  }
}
