package com.ada.conversation.infrastructure.in.rest.filter;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.ChatRequest;
import java.util.List;
import org.junit.jupiter.api.Test;

class NormalizeChatRequestFilterTest {
  @Test
  void preservesPreloadedContext() {
    var result =
        new NormalizeChatRequestFilter()
            .apply(new ChatRequest("  clima  ", null, "telegram:1", List.of("Clima: 22 °C")));

    assertThat(result.message()).isEqualTo("clima");
    assertThat(result.preloadedContext()).containsExactly("Clima: 22 °C");
  }
}
