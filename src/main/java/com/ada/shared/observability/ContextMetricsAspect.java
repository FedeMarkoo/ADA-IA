package com.ada.shared.observability;

import io.micrometer.core.instrument.*; import org.aspectj.lang.*; import org.aspectj.lang.annotation.*; import org.springframework.stereotype.Component;
@Aspect @Component public class ContextMetricsAspect { private final MeterRegistry registry; public ContextMetricsAspect(MeterRegistry r){registry=r;} @Around("@within(measuredContextItem)") public Object measure(ProceedingJoinPoint jp,MeasuredContextItem a)throws Throwable{var s=Timer.start(registry);registry.counter("ada_context_item_invocations_total","component",a.value()).increment();try{return jp.proceed();}finally{s.stop(registry.timer("ada_context_item_duration_seconds","component",a.value()));}} }
