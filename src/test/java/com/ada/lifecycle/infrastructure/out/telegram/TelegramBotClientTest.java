package com.ada.lifecycle.infrastructure.out.telegram;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class TelegramBotClientTest {
  @Test
  void rejectsTelegramApiResponsesMarkedAsUnsuccessful() {
    var client = new TelegramBotClient(null, new ObjectMapper());

    assertThatThrownBy(() -> client.verifySuccessfulResponse("{\"ok\":false}"))
        .isInstanceOf(IllegalStateException.class)
        .hasMessage("Telegram rejected the message");
  }
}
