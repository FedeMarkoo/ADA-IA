package com.ada.observability.spring;

import com.ada.observability.api.AdaObservability;
import com.ada.observability.api.ExternalCall;
import java.time.Instant;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;

@ConditionalOnClass(ClientHttpRequestInterceptor.class)
public class AdaObservabilityRestTemplateInterceptor implements ClientHttpRequestInterceptor {
  private final AdaObservability observability;
  public AdaObservabilityRestTemplateInterceptor(AdaObservability observability) { this.observability = observability; }
  @Override public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution) throws java.io.IOException {
    String correlation = observability.currentTrace() == null ? null : observability.currentTrace().correlationId();
    if (correlation != null) {
      request.getHeaders().set("x-ada-correlationid", correlation);
      request.getHeaders().set("x-ada-caller", observability.currentTrace().caller());
      request.getHeaders().set("x-ada-ini-caller", observability.currentTrace().initialCaller());
    }
    Instant begin = Instant.now();
    try {
      ClientHttpResponse response = execution.execute(request, body);
      add(new ExternalCall(request.getURI().toString(), request.getMethod().name(), response.getStatusCode().value(), null, null, begin, Instant.now(), null, null));
      return response;
    } catch (RuntimeException | java.io.IOException error) {
      add(new ExternalCall(request.getURI().toString(), request.getMethod().name(), null, null, null, begin, Instant.now(), error.toString(), null));
      throw error;
    }
  }
  private void add(ExternalCall call) { observability.recordExternalCall(call); }
}
