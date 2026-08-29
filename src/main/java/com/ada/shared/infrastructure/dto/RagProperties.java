package com.ada.shared.infrastructure.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class RagProperties {
  private boolean enabled = true;

  @Min(1) @Max(20) private int topK = 5;

  @Min(256) @Max(12000) private int maxContextCharacters = 6000;
}
