package com.ada.lifecycle.infrastructure.in;

import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class TelegramSecretInitializer implements ApplicationRunner {
  private static final String BOT_TOKEN = "telegram.bot-token";
  private static final String CHAT_ID = "telegram.chat-id";

  private final SecretStore secretStore;
  private final AdaProperties properties;

  @Override
  public void run(ApplicationArguments args) {
    var telegram = properties.getTelegram();
    if (telegram == null || !telegram.isEnabled()) return;
    secretStore.saveIfAbsent(BOT_TOKEN, telegram.getBootstrapBotToken());
    secretStore.saveIfAbsent(CHAT_ID, telegram.getBootstrapChatId());
  }
}
