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
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.sqlite.SQLiteDataSource;

class SqliteRagDocumentStoreTest {
  @TempDir java.nio.file.Path tempDir;

  @Test
  void storesAndSearchesDocumentsInConversationScope() throws Exception {
    var dataSource = new SQLiteDataSource();
    dataSource.setUrl("jdbc:sqlite:" + Files.createTempFile(tempDir, "rag", ".sqlite"));
    try (var connection = dataSource.getConnection()) {
      ScriptUtils.executeSqlScript(connection, new ClassPathResource("schema.sql"));
      var store =
          new SqliteRagDocumentStore(
              new JdbcTemplate(new SingleConnectionDataSource(connection, false)));

      var firstId = store.save("conversation-1", "guide.md", "ADA is local-first");
      store.save("conversation-2", "other.md", "ADA is local-first");

      assertThat(firstId).isPositive();
      assertThat(store.search("conversation-1", "local-first", 5))
          .extracting(RagDocument::source)
          .containsExactly("guide.md");
      assertThat(store.search("conversation-1", "local-first OR \"*\"", 5)).hasSize(1);
      assertThat(store.search("conversation-1", "local-first", 0)).isEmpty();
    }
  }
}
