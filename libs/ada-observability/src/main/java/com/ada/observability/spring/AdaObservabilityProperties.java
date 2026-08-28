package com.ada.observability.spring;

import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("ada.observability")
public class AdaObservabilityProperties {
  private boolean enabled = true;
  private String applicationName = "${spring.application.name:ada}";
  private List<String> hiddenFields =
      new ArrayList<>(List.of("authorization", "token", "password", "apiKey", "client_secret"));
  private List<String> ignoredPaths =
      new ArrayList<>(List.of("/actuator/health", "/actuator/metrics"));

  public boolean isEnabled() {
    return enabled;
  }

  public void setEnabled(boolean enabled) {
    this.enabled = enabled;
  }

  public String getApplicationName() {
    return applicationName;
  }

  public void setApplicationName(String applicationName) {
    this.applicationName = applicationName;
  }

  public List<String> getHiddenFields() {
    return hiddenFields;
  }

  public void setHiddenFields(List<String> hiddenFields) {
    this.hiddenFields = hiddenFields;
  }

  public List<String> getIgnoredPaths() {
    return ignoredPaths;
  }

  public void setIgnoredPaths(List<String> ignoredPaths) {
    this.ignoredPaths = ignoredPaths;
  }
}
