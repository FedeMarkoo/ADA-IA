package com.ada.model.adapters.out

import com.ada.conversation.application.port.out.LlmClient
import com.ada.conversation.application.port.out.LlmCompletion
import com.ada.conversation.application.port.out.LlmMessageRole
import com.ada.conversation.application.port.out.LlmRequest
import com.ada.shared.infrastructure.AdaProperties
import com.ada.shared.observability.AdaMetrics
import com.fasterxml.jackson.annotation.JsonProperty
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
                messages = request.messages.map { LiteLlmMessage(it.role.wireName(), it.content) },
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

private fun LlmMessageRole.wireName(): String = name.lowercase()

private data class LiteLlmRequest(
    val model: String,
    val messages: List<LiteLlmMessage>,
    val tools: List<LiteLlmTool> = emptyList(),
    val temperature: Double? = null,
    @JsonProperty("max_tokens") val maxTokens: Int? = null,
)

private data class LiteLlmMessage(val role: String, val content: String)

private data class LiteLlmTool(
    val name: String,
    val description: String,
    @JsonProperty("input_schema") val inputSchema: String,
)

private data class LiteLlmResponse(
    val model: String? = null,
    val choices: List<LiteLlmChoice> = emptyList(),
    val usage: LiteLlmUsage? = null,
)

private data class LiteLlmChoice(val message: LiteLlmMessage)

private data class LiteLlmUsage(
    @JsonProperty("prompt_tokens")
    val promptTokens: Long? = null,
    @JsonProperty("completion_tokens")
    val completionTokens: Long? = null,
)
