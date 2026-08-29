package com.ada.conversation.infrastructure.rag;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.RagDocument;
import com.ada.conversation.infrastructure.out.rag.SqliteRagDocumentStore;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
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
      jdbc.execute(
          "CREATE TABLE rag_documents (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, source TEXT NOT NULL, content TEXT NOT NULL)");
      jdbc.execute(
          "CREATE VIRTUAL TABLE rag_documents_fts USING fts5(source, content, content='rag_documents', content_rowid='id')");
      jdbc.execute(
          "CREATE TRIGGER rag_documents_ai AFTER INSERT ON rag_documents BEGIN INSERT INTO rag_documents_fts(rowid, source, content) VALUES (new.id, new.source, new.content); END");
      var store = new SqliteRagDocumentStore(jdbc);

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
