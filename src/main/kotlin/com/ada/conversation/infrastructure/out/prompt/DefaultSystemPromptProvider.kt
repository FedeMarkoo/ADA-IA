package com.ada.conversation.infrastructure.out.prompt

import com.ada.conversation.application.SystemPromptProvider
import org.springframework.stereotype.Component

@Component
class DefaultSystemPromptProvider : SystemPromptProvider {
    override fun content(): String = "You are ADA, a local-first assistant. Protect privacy and explain actions clearly."
}
