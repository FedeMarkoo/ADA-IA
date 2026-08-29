package com.ada.conversation.manager;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.RagDocument;
import com.ada.conversation.application.port.out.RagDocumentStore;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.dto.RagProperties;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class RagManagerTest {
  @Test
  void retrievesConfiguredDocuments() {
    var store = Mockito.mock(RagDocumentStore.class);
    var properties = new AdaProperties();
    var rag = new RagProperties();
    rag.setTopK(3);
    properties.setRag(rag);
    Mockito.when(store.search("conversation-1", "qué sé de Ada", 3))
        .thenReturn(List.of(new RagDocument(1, "guide.md", "Ada es local-first")));
    var manager = new RagManager(store, properties);

    assertThat(manager.retrieve(new ChatRequest("qué sé de Ada", null, "conversation-1")))
        .extracting(RagDocument::content)
        .containsExactly("Ada es local-first");
    Mockito.verify(store).search("conversation-1", "qué sé de Ada", 3);
  }

  @Test
  void doesNotRetrieveWhenDisabled() {
    var store = Mockito.mock(RagDocumentStore.class);
    var properties = new AdaProperties();
    var rag = new RagProperties();
    rag.setEnabled(false);
    properties.setRag(rag);

    assertThat(new RagManager(store, properties).retrieve(new ChatRequest("consulta", null)))
        .isEmpty();
    Mockito.verifyNoInteractions(store);
  }

  @Test
  void rejectsBlankDocuments() {
    var manager = new RagManager(Mockito.mock(RagDocumentStore.class), new AdaProperties());

    assertThatThrownBy(() -> manager.index("", "source", "body"))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
