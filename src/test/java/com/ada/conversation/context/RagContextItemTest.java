package com.ada.conversation.context;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.ContextState;
import com.ada.conversation.application.dto.LlmMessageRole;
import com.ada.conversation.application.dto.RagDocument;
import com.ada.conversation.application.port.out.RagDocumentStore;
import com.ada.conversation.manager.RagManager;
import com.ada.shared.infrastructure.AdaProperties;
import java.util.List;
import org.junit.jupiter.api.Test;

class RagContextItemTest {
  @Test
  void emitsRetrievedDataAsUserMessageAndRespectsContextLimit() {
    var properties = new AdaProperties();
    var rag = new com.ada.shared.infrastructure.dto.RagProperties();
    rag.setMaxContextCharacters(180);
    properties.setRag(rag);
    RagDocumentStore store =
        new RagDocumentStore() {
          public long save(String conversationId, String source, String content) {
            return 1;
          }

          public List<RagDocument> search(String conversationId, String query, int limit) {
            return List.of(new RagDocument(1, "guide.md", "A".repeat(500)));
          }
        };

    var result =
        new RagContextItem(new RagManager(store, properties), properties)
            .apply(new ChatRequest("query", null, "conversation-1"), new ContextState());

    assertThat(result.messages()).hasSize(1);
    assertThat(result.messages().getFirst().role()).isEqualTo(LlmMessageRole.USER);
    assertThat(result.messages().getFirst().content()).hasSize(180);
    assertThat(result.messages().getFirst().content()).contains("guide.md");
  }
}
