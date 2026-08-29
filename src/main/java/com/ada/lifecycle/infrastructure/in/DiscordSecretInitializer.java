package com.ada.lifecycle.infrastructure.in;

import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class DiscordSecretInitializer implements ApplicationRunner {
  static final String BOT_TOKEN = "discord.bot-token";
  static final String CHANNEL_ID = "discord.channel-id";

  private final SecretStore secretStore;
  private final AdaProperties properties;

  @Override
  public void run(ApplicationArguments args) {
    var discord = properties.getDiscord();
    if (discord == null || !discord.isEnabled()) return;
    secretStore.saveIfAbsent(BOT_TOKEN, discord.getBootstrapBotToken());
    secretStore.saveIfAbsent(CHANNEL_ID, discord.getBootstrapChannelId());
  }
}
