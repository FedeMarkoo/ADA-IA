package com.ada.lifecycle.infrastructure.in;

import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatRequest;
import com.ada.lifecycle.infrastructure.out.telegram.TelegramBotClient;
import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import java.util.concurrent.atomic.AtomicBoolean;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import jakarta.annotation.PreDestroy;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;

@Component
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "ada.telegram", name = "enabled", havingValue = "true")
public class TelegramMessageListener {
  private static final Logger log = LoggerFactory.getLogger(TelegramMessageListener.class);
  private final ChatUseCase chatUseCase;
  private final TelegramBotClient telegram;
  private final SecretStore secretStore;
  private final AdaProperties properties;
  private final AtomicBoolean running = new AtomicBoolean();
  private volatile Thread worker;

  @EventListener(ApplicationReadyEvent.class)
  public void start() {
    if (!running.compareAndSet(false, true)) return;
    worker = Thread.ofVirtual().name("ada-telegram-listener").start(this::poll);
  }

  @PreDestroy
  public void stop() {
    running.set(false);
    var current = worker;
    if (current != null) current.interrupt();
  }

  private void poll() {
    var token = secretStore.find("telegram.bot-token").orElse(null);
    var chatId = secretStore.find("telegram.chat-id").orElse(null);
    if (isBlank(token) || isBlank(chatId)) {
      log.warn("Telegram inbound messages are enabled but not configured");
      running.set(false);
      return;
    }

    long offset = 0;
    while (running.get()) {
      try {
        var timeout = properties.getTelegram().getPollingTimeoutSeconds();
        for (var update : telegram.getUpdates(token, offset, timeout)) {
          offset = Math.max(offset, update.updateId() + 1);
          processUpdate(token, chatId, update);
        }
      } catch (RestClientException | java.io.IOException exception) {
        if (running.get()) {
          log.warn("Telegram polling failed; retrying");
          pauseBeforeRetry();
        }
      }
    }
  }

  void processUpdate(
      String token,
      String chatId,
      com.ada.lifecycle.infrastructure.out.telegram.TelegramUpdate update) {
    if (!chatId.equals(update.chatId())) return;
    respond(token, chatId, update.text());
  }

  private void respond(String token, String chatId, String text) {
    try {
      var result = chatUseCase.execute(new ChatRequest(text, null, "telegram:" + chatId));
      telegram.sendMessage(token, chatId, result.content());
    } catch (RuntimeException exception) {
      log.warn("Could not process Telegram message");
      try {
        telegram.sendMessage(token, chatId, "No pude procesar el mensaje. Intentá de nuevo.");
      } catch (RestClientException ignored) {
        log.warn("Could not send Telegram error response");
      }
    }
  }

  private void pauseBeforeRetry() {
    try {
      Thread.sleep(5000);
    } catch (InterruptedException exception) {
      Thread.currentThread().interrupt();
      running.set(false);
    }
  }

  private boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
