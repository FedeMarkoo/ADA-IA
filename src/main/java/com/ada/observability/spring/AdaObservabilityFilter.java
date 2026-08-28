package com.ada.observability.spring;

import com.ada.observability.api.AdaObservability;
import com.ada.observability.api.TraceContext;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.web.filter.OncePerRequestFilter;

@ConditionalOnClass(OncePerRequestFilter.class)
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AdaObservabilityFilter extends OncePerRequestFilter {
  private final AdaObservability observability;
  private final AdaObservabilityProperties properties;
  public AdaObservabilityFilter(AdaObservability observability, AdaObservabilityProperties properties) { this.observability = observability; this.properties = properties; }
  @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
    if (properties.getIgnoredPaths().contains(request.getRequestURI())) { chain.doFilter(request, response); return; }
    String correlation = request.getHeader("x-ada-correlationid");
    TraceContext trace = TraceContext.create(properties.getApplicationName(), correlation, request.getHeader("x-ada-caller"), request.getHeader("x-ada-ini-caller"));
    try (var scope = observability.start(request.getMethod() + " " + request.getRequestURI(), "REST", trace)) {
      scope.event("originIp", request.getRemoteAddr());
      try { chain.doFilter(request, response); scope.status(response.getStatus()); }
      catch (RuntimeException | IOException | ServletException error) { scope.failure(error); scope.status(response.getStatus()); throw error; }
      response.setHeader("x-ada-correlationid", scope.snapshot().getTrace().correlationId());
      response.setHeader("x-ada-caller", trace.caller());
      response.setHeader("x-ada-ini-caller", trace.initialCaller());
    }
  }
}
