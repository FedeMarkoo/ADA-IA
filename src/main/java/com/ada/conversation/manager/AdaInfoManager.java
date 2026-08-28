package com.ada.conversation.manager;

import java.util.Locale;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
@NoArgsConstructor
public class AdaInfoManager {
  @Value("${spring.application.name:ada}")
  private String applicationName;

  @Value("${ADA_DEPLOYED_VERSION:latest}")
  private String deployedVersion;

  @Value("${ADA_COMMIT_ID:${ADA_BUILD_COMMIT_ID:unknown}}")
  private String commitId;

  @Value("${ada.llm.default-model:unknown}")
  private String defaultModel;

  public boolean supports(String message) {
    return "/i".equalsIgnoreCase(message.trim());
  }

  public String describe() {
    return "ADA\n"
        + "application="
        + applicationName
        + "\nversion="
        + deployedVersion
        + "\ncommit="
        + commitId
        + "\nmodel="
        + defaultModel
        + "\njava="
        + Runtime.version().feature()
        + "\nos="
        + System.getProperty("os.name").toLowerCase(Locale.ROOT)
        + "\narch="
        + System.getProperty("os.arch");
  }
}
