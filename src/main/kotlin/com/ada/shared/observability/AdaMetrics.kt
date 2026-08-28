package com.ada.shared.observability

import io.micrometer.core.instrument.MeterRegistry
import io.micrometer.core.instrument.Timer
import org.springframework.stereotype.Component

@Component
class AdaMetrics(private val registry: MeterRegistry) {
    fun recordRequest(context: String, useCase: String, outcome: String) {
        registry.counter("ada_requests_total", "context", context, "use_case", useCase, "outcome", outcome).increment()
    }

    fun recordTokens(model: String, input: Long?, output: Long?) {
        input?.let { registry.counter("ada_llm_tokens_total", "model", model, "direction", "input").increment(it.toDouble()) }
        output?.let { registry.counter("ada_llm_tokens_total", "model", model, "direction", "output").increment(it.toDouble()) }
    }

    fun <T> measureLlm(model: String, operation: () -> T): T {
        val sample = Timer.start(registry)
        return try {
            operation()
        } finally {
            sample.stop(registry.timer("ada_llm_duration_seconds", "model", model))
        }
    }
}
