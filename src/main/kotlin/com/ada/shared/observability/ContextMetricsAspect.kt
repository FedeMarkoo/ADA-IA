package com.ada.shared.observability

import io.micrometer.core.instrument.MeterRegistry
import io.micrometer.core.instrument.Timer
import org.aspectj.lang.ProceedingJoinPoint
import org.aspectj.lang.annotation.Around
import org.aspectj.lang.annotation.Aspect
import org.springframework.stereotype.Component

@Aspect
@Component
class ContextMetricsAspect(
    private val registry: MeterRegistry,
) {
    @Around("@within(measuredContextItem)")
    fun measure(joinPoint: ProceedingJoinPoint, measuredContextItem: MeasuredContextItem): Any? {
        val sample = Timer.start(registry)
        val tags = arrayOf("component", measuredContextItem.component)
        registry.counter("ada_context_item_invocations_total", *tags).increment()
        return try {
            joinPoint.proceed()
        } finally {
            sample.stop(registry.timer("ada_context_item_duration_seconds", *tags))
        }
    }
}
