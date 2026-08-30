package com.ada.lifecycle.infrastructure.out.telegram;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.anything;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class TelegramBotClientTest {
  @Test
  void rejectsTelegramApiResponsesMarkedAsUnsuccessful() {
    var builder = RestClient.builder();
    var server = MockRestServiceServer.bindTo(builder).build();
    var client = new TelegramBotClient(builder, new ObjectMapper());
    server
        .expect(anything())
        .andRespond(withSuccess("{\"ok\":false}", MediaType.APPLICATION_JSON));

    assertThatThrownBy(() -> client.sendMessage("token", "chat", "mensaje"))
        .isInstanceOf(IllegalStateException.class)
        .hasMessage("Telegram rejected the message");

    server.verify();
  }
}
