package com.ada.observability.spring;

import com.ada.observability.api.AdaObservability;
import com.ada.observability.api.OperationLog;
import com.ada.observability.core.DefaultAdaObservability;
import com.ada.observability.core.Redactor;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.MeterRegistry;
import java.util.logging.Logger;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.web.client.RestTemplateCustomizer;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@EnableConfigurationProperties(AdaObservabilityProperties.class)
@ConditionalOnClass(ObjectMapper.class)
public class AdaObservabilityAutoConfiguration {
  private static final Logger LOGGER =
      Logger.getLogger(AdaObservabilityAutoConfiguration.class.getName());

  @Bean
  @ConditionalOnMissingBean
  Redactor adaRedactor(ObjectMapper mapper, AdaObservabilityProperties properties) {
    return new Redactor(mapper, properties.getHiddenFields());
  }

  @Bean
  @ConditionalOnMissingBean
  AdaObservability adaObservability(
      AdaObservabilityProperties properties,
      Redactor redactor,
      ObjectProvider<MeterRegistry> registry) {
    return new DefaultAdaObservability(
        properties.getApplicationName(), log -> emit(log, redactor, registry.getIfAvailable()));
  }

  @Bean
  @ConditionalOnWebApplication
  @ConditionalOnClass(name = "org.springframework.web.filter.OncePerRequestFilter")
  AdaObservabilityFilter adaObservabilityFilter(
      AdaObservability observability, AdaObservabilityProperties properties) {
    return new AdaObservabilityFilter(observability, properties);
  }

  @Bean
  @ConditionalOnClass(name = "org.springframework.http.client.ClientHttpRequestInterceptor")
  AdaObservabilityRestTemplateInterceptor adaObservabilityRestTemplateInterceptor(
      AdaObservability observability) {
    return new AdaObservabilityRestTemplateInterceptor(observability);
  }

  @Bean
  @ConditionalOnClass(name = "org.springframework.web.client.RestTemplate")
  RestTemplateCustomizer adaObservabilityRestTemplateCustomizer(
      AdaObservabilityRestTemplateInterceptor interceptor) {
    return restTemplate -> restTemplate.getInterceptors().add(interceptor);
  }

  private void emit(OperationLog log, Redactor redactor, MeterRegistry registry) {
    String json = redactor.json(log);
    if (log.getExceptionMessage() != null
        || (log.getStatusCode() != null && log.getStatusCode() >= 500)) LOGGER.warning(json);
    else LOGGER.info(json);
    if (registry != null)
      registry
          .timer("ada.operation.duration", "kind", log.getKind(), "operation", log.getOperation())
          .record(log.getDuration(), java.util.concurrent.TimeUnit.MILLISECONDS);
  }
}
