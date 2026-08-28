package com.ada.lifecycle.infrastructure.out.telegram;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@RequiredArgsConstructor
public class TelegramBotClient {
  private final RestClient.Builder restClientBuilder;
  private final ObjectMapper objectMapper;

  public void sendMessage(String token, String chatId, String text) {
    client(token)
        .post()
        .uri("/sendMessage")
        .contentType(MediaType.APPLICATION_JSON)
        .body(new TelegramMessage(chatId, text))
        .retrieve()
        .toBodilessEntity();
  }

  public List<TelegramUpdate> getUpdates(String token, long offset, int timeoutSeconds)
      throws JsonProcessingException {
    var body =
        client(token)
            .get()
            .uri(
                builder ->
                    builder
                        .path("/getUpdates")
                        .queryParam("offset", offset)
                        .queryParam("timeout", timeoutSeconds)
                        .build())
            .retrieve()
            .body(String.class);
    return parseUpdates(body);
  }

  private List<TelegramUpdate> parseUpdates(String body) throws JsonProcessingException {
    JsonNode root = objectMapper.readTree(body);
    var updates = new ArrayList<TelegramUpdate>();
    for (var item : root.path("result")) {
      var message = item.path("message");
      var chat = message.path("chat");
      var text = message.path("text");
      if (message.isMissingNode() || chat.isMissingNode() || !text.isTextual()) continue;
      updates.add(
          new TelegramUpdate(
              item.path("update_id").asLong(), chat.path("id").asText(), text.asText()));
    }
    return updates;
  }

  private RestClient client(String token) {
    var requestFactory =
        new JdkClientHttpRequestFactory(
            HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());
    requestFactory.setReadTimeout(Duration.ofSeconds(35));
    return restClientBuilder
        .requestFactory(requestFactory)
        .baseUrl("https://api.telegram.org/bot" + token)
        .build();
  }
}
