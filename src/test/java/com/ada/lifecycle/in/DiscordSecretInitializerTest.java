package com.ada.lifecycle.infrastructure.in;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.dto.DiscordProperties;
import org.junit.jupiter.api.Test;

class DiscordSecretInitializerTest {
  private final SecretStore secretStore = org.mockito.Mockito.mock(SecretStore.class);
  private final AdaProperties properties = new AdaProperties();

  @Test
  void persistsOnlyNonBlankBootstrapValuesWhenDiscordIsEnabled() {
    var discord = new DiscordProperties();
    discord.setEnabled(true);
    discord.setBootstrapBotToken("bot-token");
    discord.setBootstrapChannelId("  ");
    properties.setDiscord(discord);

    new DiscordSecretInitializer(secretStore, properties).run(null);

    verify(secretStore).saveIfAbsent("discord.bot-token", "bot-token");
    verify(secretStore, never()).saveIfAbsent("discord.channel-id", "  ");
  }

  @Test
  void doesNotPersistBootstrapValuesWhenDiscordIsDisabled() {
    var discord = new DiscordProperties();
    discord.setBootstrapBotToken("bot-token");
    discord.setBootstrapChannelId("channel-id");
    properties.setDiscord(discord);

    new DiscordSecretInitializer(secretStore, properties).run(null);

    verifyNoInteractions(secretStore);
  }

  @Test
  void doesNotPersistBootstrapValuesWhenDiscordIsNotConfigured() {
    new DiscordSecretInitializer(secretStore, properties).run(null);

    verifyNoInteractions(secretStore);
  }
}
