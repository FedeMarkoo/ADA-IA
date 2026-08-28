package com.ada.model.infrastructure.out

import com.ada.conversation.application.port.out.LlmClient
import com.ada.dto.LlmRequest
import com.ada.dto.LlmCompletion
import com.ada.dto.LiteLlmChoice
import com.ada.dto.LiteLlmMessage
import com.ada.dto.LiteLlmRequest
import com.ada.dto.LiteLlmResponse
import com.ada.dto.LiteLlmTool
import com.ada.dto.LiteLlmUsage
import com.ada.shared.infrastructure.AdaProperties
import com.ada.shared.observability.AdaMetrics
import org.springframework.http.MediaType
import org.springframework.stereotype.Component
import org.springframework.web.client.RestClient

@Component
class LiteLlmClient(
    builder: RestClient.Builder,
    private val properties: AdaProperties,
    private val metrics: AdaMetrics,
) : LlmClient {
    private val client = builder.baseUrl(properties.llm.baseUrl).build()

    override fun complete(request: LlmRequest): LlmCompletion {
        val response = client.post()
            .uri("/v1/chat/completions")
            .contentType(MediaType.APPLICATION_JSON)
            .headers { headers ->
                if (properties.llm.apiKey.isNotBlank()) {
                    headers.setBearerAuth(properties.llm.apiKey)
                }
            }
            .body(LiteLlmRequest(
                model = request.model,
                messages = request.messages.map { LiteLlmMessage(it.role.name.lowercase(), it.content) },
                tools = request.tools.map { LiteLlmTool(it.name, it.description, it.inputSchema) },
                temperature = request.temperature,
                maxTokens = request.maxTokens,
            ))
            .retrieve()
            .body(LiteLlmResponse::class.java)
            ?: error("LiteLLM returned an empty response")

        val choice = response.choices.firstOrNull() ?: error("LiteLLM returned no choices")
        metrics.recordProviderTokens(request.model, response.usage?.promptTokens, response.usage?.completionTokens)
        return LlmCompletion(
            content = choice.message.content,
            model = response.model ?: request.model,
            inputTokens = response.usage?.promptTokens,
            outputTokens = response.usage?.completionTokens,
        )
    }
}
