package com.ada.lifecycle.infrastructure.out.telegram;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.dto.TelegramProperties;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class TelegramLifecycleMessageSenderTest {
  private final TelegramBotClient telegram = org.mockito.Mockito.mock(TelegramBotClient.class);
  private final SecretStore secretStore = org.mockito.Mockito.mock(SecretStore.class);
  private final AdaProperties properties = new AdaProperties();

  @Test
  void sendsWhenTelegramIsEnabledAndConfigured() {
    var telegramProperties = new TelegramProperties();
    telegramProperties.setEnabled(true);
    properties.setTelegram(telegramProperties);
    when(secretStore.find("telegram.bot-token")).thenReturn(Optional.of("token"));
    when(secretStore.find("telegram.chat-id")).thenReturn(Optional.of("chat"));

    new TelegramLifecycleMessageSender(telegram, secretStore, properties).send("ADA inició");

    verify(telegram).sendMessage("token", "chat", "ADA inició");
  }

  @Test
  void skipsWhenTelegramIsDisabled() {
    var telegramProperties = new TelegramProperties();
    telegramProperties.setEnabled(false);
    properties.setTelegram(telegramProperties);

    new TelegramLifecycleMessageSender(telegram, secretStore, properties).send("ADA inició");

    verifyNoInteractions(telegram, secretStore);
  }
}
