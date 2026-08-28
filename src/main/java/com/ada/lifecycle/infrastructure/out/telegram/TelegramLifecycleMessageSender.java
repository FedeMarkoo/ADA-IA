package com.ada.lifecycle.infrastructure.out.telegram;

import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;

@Component
@RequiredArgsConstructor
public class TelegramLifecycleMessageSender implements LifecycleMessageSender {
  private static final Logger log = LoggerFactory.getLogger(TelegramLifecycleMessageSender.class);

  private final TelegramBotClient telegram;
  private final SecretStore secretStore;
  private final AdaProperties properties;

  @Override
  public void send(String message) {
    var telegramProperties = properties.getTelegram();
    if (telegramProperties == null || !telegramProperties.isEnabled()) return;
    var token = secretStore.find("telegram.bot-token").orElse(null);
    var chatId = secretStore.find("telegram.chat-id").orElse(null);
    if (isBlank(token) || isBlank(chatId)) {
      log.warn("Telegram lifecycle notifications are enabled but not configured");
      return;
    }

    try {
      telegram.sendMessage(token, chatId, message);
    } catch (RestClientException exception) {
      log.warn("Could not send ADA lifecycle notification to Telegram");
    }
  }

  private boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
