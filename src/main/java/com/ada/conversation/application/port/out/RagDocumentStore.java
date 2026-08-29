package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.RagDocument;
import java.util.List;

public interface RagDocumentStore {
  long save(String conversationId, String source, String content);

  List<RagDocument> search(String conversationId, String query, int limit);
}
