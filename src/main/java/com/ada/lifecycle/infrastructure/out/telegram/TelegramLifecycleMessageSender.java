package com.ada.lifecycle.infrastructure.out.telegram;

import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import com.ada.lifecycle.infrastructure.out.telegram.dto.TelegramMessage;
import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import java.net.http.HttpClient;
import java.time.Duration;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

@Component
@RequiredArgsConstructor
public class TelegramLifecycleMessageSender implements LifecycleMessageSender {
  private static final Logger log = LoggerFactory.getLogger(TelegramLifecycleMessageSender.class);

  private final RestClient.Builder restClientBuilder;
  private final SecretStore secretStore;
  private final AdaProperties properties;

  @Override
  public void send(String message) {
    var telegram = properties.getTelegram();
    if (telegram == null || !telegram.isEnabled()) return;
    var token = secretStore.find("telegram.bot-token").orElse(null);
    var chatId = secretStore.find("telegram.chat-id").orElse(null);
    if (isBlank(token) || isBlank(chatId)) {
      log.warn("Telegram lifecycle notifications are enabled but not configured");
      return;
    }

    try {
      var requestFactory =
          new JdkClientHttpRequestFactory(
              HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());
      requestFactory.setReadTimeout(Duration.ofSeconds(5));
      restClientBuilder
          .requestFactory(requestFactory)
          .baseUrl("https://api.telegram.org/bot" + token)
          .build()
          .post()
          .uri("/sendMessage")
          .contentType(MediaType.APPLICATION_JSON)
          .body(new TelegramMessage(chatId, message))
          .retrieve()
          .toBodilessEntity();
    } catch (RestClientException exception) {
      log.warn("Could not send ADA lifecycle notification to Telegram");
    }
  }

  private boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
