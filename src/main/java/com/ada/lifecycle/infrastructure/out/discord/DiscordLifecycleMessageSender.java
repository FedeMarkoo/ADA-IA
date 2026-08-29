package com.ada.lifecycle.infrastructure.out.discord;

import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class DiscordLifecycleMessageSender implements LifecycleMessageSender {
  private static final Logger log = LoggerFactory.getLogger(DiscordLifecycleMessageSender.class);
  private final DiscordBotClient discord;
  private final SecretStore secretStore;
  private final AdaProperties properties;

  @Override public void send(String message) {
    var p = properties.getDiscord();
    if (p == null || !p.isEnabled() || !p.isSendLifecycleNotifications()) return;
    var token = secretStore.find("discord.bot-token").orElse(null);
    var channel = secretStore.find("discord.channel-id").orElse(null);
    if (token == null || token.isBlank() || channel == null || channel.isBlank()) return;
    try { discord.sendMessage(token, channel, message); }
    catch (RuntimeException exception) { log.warn("Could not send ADA lifecycle notification to Discord"); }
  }
}
