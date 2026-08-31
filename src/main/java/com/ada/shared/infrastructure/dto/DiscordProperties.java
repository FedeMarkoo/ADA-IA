package com.ada.shared.infrastructure.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class DiscordProperties {
  private boolean enabled;
  private String bootstrapBotToken;
  private String bootstrapChannelId;
  private boolean sendLifecycleNotifications = true;
}
