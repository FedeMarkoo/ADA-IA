package com.ada.shared.infrastructure.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class LlmProperties {
  private String baseUrl;
  private String apiKey;
  private String defaultModel;
  private String routingModel;

  public LlmProperties(String baseUrl, String apiKey, String defaultModel) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
    this.defaultModel = defaultModel;
    this.routingModel = defaultModel;
  }
}
