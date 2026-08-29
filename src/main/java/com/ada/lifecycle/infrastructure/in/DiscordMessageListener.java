package com.ada.lifecycle.infrastructure.in;

import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatRequest;
import com.ada.lifecycle.infrastructure.out.discord.DiscordBotClient;
import com.ada.shared.application.port.out.SecretStore;
import com.fasterxml.jackson.databind.JsonNode;
import java.net.http.WebSocket;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;

@Component
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "ada.discord", name = "enabled", havingValue = "true")
public class DiscordMessageListener {
  private static final Logger log = LoggerFactory.getLogger(DiscordMessageListener.class);
  private final ChatUseCase chatUseCase;
  private final DiscordBotClient discord;
  private final SecretStore secretStore;
  private final AtomicBoolean running = new AtomicBoolean();
  private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
  private volatile WebSocket socket;

  @EventListener(ApplicationReadyEvent.class)
  public void start() {
    if (!running.compareAndSet(false, true)) return;
    var token = secretStore.find("discord.bot-token").orElse(null);
    if (isBlank(token) || isBlank(channelId())) {
      log.warn("Discord messages are enabled but bot token or channel ID is not configured");
      running.set(false);
      return;
    }
    discord.connect(token, new GatewayListener(token));
  }

  @jakarta.annotation.PreDestroy
  public void stop() {
    running.set(false);
    scheduler.shutdownNow();
    var current = socket;
    if (current != null) current.sendClose(WebSocket.NORMAL_CLOSURE, "shutdown");
  }

  private String channelId() { return secretStore.find("discord.channel-id").orElse(null); }

  private final class GatewayListener implements WebSocket.Listener {
    private final String token;
    private volatile long sequence = -1;

    private GatewayListener(String token) { this.token = token; }

    @Override public void onOpen(WebSocket webSocket) {
      socket = webSocket;
      webSocket.request(1);
    }

    @Override public java.util.concurrent.CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
      try {
        JsonNode event = discord.read(data.toString());
        if (event.has("s") && !event.get("s").isNull()) sequence = event.get("s").asLong();
        int op = event.path("op").asInt();
        if (op == 10) identify(webSocket, event.path("d").path("heartbeat_interval").asLong());
        if (op == 0 && "MESSAGE_CREATE".equals(event.path("t").asText())) process(event.path("d"));
      } catch (Exception exception) { log.warn("Could not process Discord gateway event"); }
      webSocket.request(1);
      return null;
    }

    private void identify(WebSocket webSocket, long interval) throws Exception {
      webSocket.sendText(discord.json(new DiscordGatewayPayload(2, java.util.Map.of(
          "token", token, "intents", 33281, "properties", java.util.Map.of("os", "linux", "browser", "ada", "device", "ada")))), true);
      scheduler.scheduleAtFixedRate(() -> webSocket.sendText(heartbeat(), true), interval, interval, TimeUnit.MILLISECONDS);
    }

    private String heartbeat() {
      try { return discord.json(new DiscordGatewayPayload(1, sequence < 0 ? null : sequence)); }
      catch (Exception exception) { return "{\"op\":1,\"d\":null}"; }
    }
  }

  void process(JsonNode message) {
    if (!channelId().equals(message.path("channel_id").asText()) || message.path("author").path("bot").asBoolean()) return;
    var text = message.path("content").asText("");
    if (text.isBlank()) return;
    try {
      var result = chatUseCase.execute(new ChatRequest(text, null, "discord:" + channelId()));
      discord.sendMessage(secretStore.find("discord.bot-token").orElseThrow(), channelId(), result.content());
    } catch (RuntimeException exception) {
      log.warn("Could not process Discord message");
      try { discord.sendMessage(secretStore.find("discord.bot-token").orElseThrow(), channelId(), "No pude procesar el mensaje. Intentá de nuevo."); }
      catch (RestClientException ignored) { log.warn("Could not send Discord error response"); }
    }
  }

  private boolean isBlank(String value) { return value == null || value.isBlank(); }
}
