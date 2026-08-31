package com.ada.conversation.application.dto;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class ContextSelectionTest {
  @Test
  void copiesSelectionListsToKeepContextImmutable() {
    var tools = new ArrayList<>(List.of("web_search"));
    var selection = new ContextSelection(List.of("web"), tools, List.of("preferences"), false);
    tools.add("unexpected");

    assertThat(selection.tools()).containsExactly("web_search");
    assertThat(selection.memories()).containsExactly("preferences");
  }

  @Test
  void fallbackDoesNotEnableExternalContext() {
    assertThat(ContextSelection.all(List.of(), List.of()).mcps()).isEmpty();
  }
}
