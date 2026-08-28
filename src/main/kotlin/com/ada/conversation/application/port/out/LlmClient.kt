package com.ada.conversation.application.port.out

import com.ada.conversation.application.dto.LlmCompletion
import com.ada.conversation.application.dto.LlmRequest

interface LlmClient { fun complete(request: LlmRequest): LlmCompletion }
