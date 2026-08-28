package com.ada.observability.spring;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class AdaObservabilityPropertiesTest {
  @Test
  void usesConcreteApplicationNameByDefault() {
    assertThat(new AdaObservabilityProperties().getApplicationName()).isEqualTo("ada");
  }
}
