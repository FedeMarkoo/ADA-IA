package com.ada.shared.infrastructure.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TelegramProperties {
  private boolean enabled;
  private String bootstrapBotToken;
  private String bootstrapChatId;
  private int pollingTimeoutSeconds = 25;
}
