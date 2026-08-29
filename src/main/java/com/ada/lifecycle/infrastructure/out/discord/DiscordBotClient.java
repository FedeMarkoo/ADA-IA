package com.ada.lifecycle.infrastructure.out.discord;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@RequiredArgsConstructor
public class DiscordBotClient {
  private final RestClient.Builder restClientBuilder;
  private final ObjectMapper objectMapper;

  public void sendMessage(String token, String channelId, String text) {
    client(token).post().uri("/channels/{channelId}/messages", channelId)
        .contentType(MediaType.APPLICATION_JSON)
        .body(new DiscordMessage(text)).retrieve().toBodilessEntity();
  }

  public void connect(String token, WebSocket.Listener listener) {
    HttpClient.newHttpClient().newWebSocketBuilder()
        .buildAsync(URI.create("wss://gateway.discord.gg/?v=10&encoding=json"), listener);
  }

  public JsonNode read(String payload) throws Exception {
    return objectMapper.readTree(payload);
  }

  public String json(Object value) throws Exception {
    return objectMapper.writeValueAsString(value);
  }

  private RestClient client(String token) {
    return restClientBuilder.baseUrl("https://discord.com/api/v10")
        .defaultHeader("Authorization", "Bot " + token).build();
  }

  public record DiscordMessage(String content) {}
}
