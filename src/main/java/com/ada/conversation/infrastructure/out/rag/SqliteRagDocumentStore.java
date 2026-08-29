package com.ada.conversation.infrastructure.out.rag;

import com.ada.conversation.application.dto.RagDocument;
import com.ada.conversation.application.port.out.RagDocumentStore;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class SqliteRagDocumentStore implements RagDocumentStore {
  private final JdbcTemplate jdbc;

  public SqliteRagDocumentStore(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  @Override
  public long save(String conversationId, String source, String content) {
    jdbc.update(
        "INSERT INTO rag_documents(conversation_id, source, content) VALUES (?, ?, ?)",
        conversationId,
        source,
        content);
    return jdbc.queryForObject("SELECT last_insert_rowid()", Long.class);
  }

  @Override
  public List<RagDocument> search(String conversationId, String query, int limit) {
    var match = toFtsQuery(query);
    if (match.isBlank()) return List.of();
    return jdbc.query(
        "SELECT d.id, d.source, d.content "
            + "FROM rag_documents_fts f JOIN rag_documents d ON d.id = f.rowid "
            + "WHERE d.conversation_id = ? AND rag_documents_fts MATCH ? "
            + "ORDER BY bm25(rag_documents_fts) LIMIT ?",
        (rs, rowNum) ->
            new RagDocument(rs.getLong("id"), rs.getString("source"), rs.getString("content")),
        conversationId,
        match,
        limit);
  }

  private String toFtsQuery(String query) {
    return java.util.Arrays.stream(query.trim().split("\\s+"))
        .map(token -> token.replaceAll("[^\\p{L}\\p{N}_-]", ""))
        .filter(token -> token.length() >= 2)
        .map(token -> "\"" + token.replace("\"", "") + "\"")
        .collect(java.util.stream.Collectors.joining(" OR "));
  }
}
