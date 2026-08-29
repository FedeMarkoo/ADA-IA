package com.ada.shared.infrastructure;

import com.ada.shared.infrastructure.dto.LlmProperties;
import com.ada.shared.infrastructure.dto.SecretsProperties;
import com.ada.shared.infrastructure.dto.TelegramProperties;
import com.ada.shared.infrastructure.dto.DiscordProperties;
import jakarta.validation.constraints.NotBlank;
import java.nio.file.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.NestedConfigurationProperty;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "ada")
@Getter
@Setter
@NoArgsConstructor
public class AdaProperties {
  @NotBlank private String dataDir;
  @NestedConfigurationProperty private LlmProperties llm;
  @NestedConfigurationProperty private TelegramProperties telegram;
  @NestedConfigurationProperty private DiscordProperties discord;
  @NestedConfigurationProperty private SecretsProperties secrets;

  public Path getNormalizedDataDirectory() {
    return Path.of(dataDir).toAbsolutePath().normalize();
  }
}
