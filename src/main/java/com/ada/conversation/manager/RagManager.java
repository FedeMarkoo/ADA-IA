package com.ada.conversation.manager;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.RagDocument;
import com.ada.conversation.application.port.out.RagDocumentStore;
import com.ada.shared.infrastructure.AdaProperties;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class RagManager {
  private final RagDocumentStore store;
  private final AdaProperties properties;

  public long index(String conversationId, String source, String content) {
    if (conversationId == null || conversationId.isBlank())
      throw new IllegalArgumentException("conversationId is required");
    if (source == null || source.isBlank())
      throw new IllegalArgumentException("source is required");
    if (content == null || content.isBlank())
      throw new IllegalArgumentException("content is required");
    return store.save(conversationId, source.trim(), content.trim());
  }

  public List<RagDocument> retrieve(ChatRequest request) {
    if (properties.getRag() == null || !properties.getRag().isEnabled()) return List.of();
    return store.search(request.conversationId(), request.message(), properties.getRag().getTopK());
  }
}
