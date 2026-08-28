package com.ada.lifecycle.infrastructure.in;

import static org.mockito.Mockito.verify;

import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.dto.TelegramProperties;
import org.junit.jupiter.api.Test;

class TelegramSecretInitializerTest {
  private final SecretStore secretStore = org.mockito.Mockito.mock(SecretStore.class);
  private final AdaProperties properties = new AdaProperties();

  @Test
  void persistsBootstrapValuesOnlyWhenTelegramIsEnabled() {
    var telegram = new TelegramProperties();
    telegram.setEnabled(true);
    telegram.setBootstrapBotToken("bot-token");
    telegram.setBootstrapChatId("chat-id");
    properties.setTelegram(telegram);

    new TelegramSecretInitializer(secretStore, properties).run(null);

    verify(secretStore).saveIfAbsent("telegram.bot-token", "bot-token");
    verify(secretStore).saveIfAbsent("telegram.chat-id", "chat-id");
  }
}
