package com.ada.conversation.infrastructure.rag;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.RagDocument;
import com.ada.conversation.infrastructure.out.rag.SqliteRagDocumentStore;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.sqlite.SQLiteDataSource;

class SqliteRagDocumentStoreTest {
  @TempDir java.nio.file.Path tempDir;

  @Test
  void storesAndSearchesDocumentsInConversationScope() throws Exception {
    var dataSource = new SQLiteDataSource();
    dataSource.setUrl("jdbc:sqlite:" + Files.createTempFile(tempDir, "rag", ".sqlite"));
    try (var connection = dataSource.getConnection()) {
      var jdbc = new JdbcTemplate(new SingleConnectionDataSource(connection, false));
      executeSchema(jdbc);
      var store = new SqliteRagDocumentStore(jdbc);

      var firstId = store.save("conversation-1", "guide.md", "ADA is local-first");
      store.save("conversation-1", "notes.md", "ADA is local-first too");
      var secondId = store.save("conversation-2", "other.md", "ADA is local-first");

      assertThat(firstId).isPositive();
      assertThat(store.search("conversation-1", "local-first", 5))
          .extracting(RagDocument::source)
          .containsExactlyInAnyOrder("guide.md", "notes.md");
      assertThat(store.search("conversation-1", "local-first OR \"*\"", 5)).hasSize(2);
      assertThat(store.search("conversation-1", "local-first", 1)).hasSize(1);
      assertThat(store.search("conversation-1", "local-first", 0)).isEmpty();

      jdbc.update("UPDATE rag_documents SET content = ? WHERE id = ?", "ADA is private", firstId);
      assertThat(store.search("conversation-1", "local-first", 5))
          .extracting(RagDocument::source)
          .containsExactly("notes.md");
      assertThat(store.search("conversation-1", "private", 5)).hasSize(1);

      jdbc.update("DELETE FROM rag_documents WHERE id = ?", secondId);
      assertThat(store.search("conversation-2", "local-first", 5)).isEmpty();
    }
  }

  private void executeSchema(JdbcTemplate jdbc) throws Exception {
    var sql =
        new String(
            new ClassPathResource("schema.sql").getInputStream().readAllBytes(),
            java.nio.charset.StandardCharsets.UTF_8);
    var statement = new StringBuilder();
    var triggerDepth = 0;
    for (var line : sql.split("\\R")) {
      var trimmed = line.trim();
      statement.append(line).append('\n');
      if (trimmed.startsWith("CREATE TRIGGER")) triggerDepth = 1;
      if (triggerDepth > 0 && (trimmed.equals("END;") || trimmed.equals("END;;"))) triggerDepth = 0;
      if (triggerDepth == 0 && (trimmed.endsWith(";") || trimmed.endsWith(";;"))) {
        if (trimmed.endsWith(";;")) statement.setLength(statement.length() - 1);
        jdbc.execute(statement.toString());
        statement.setLength(0);
      }
    }
  }
}
