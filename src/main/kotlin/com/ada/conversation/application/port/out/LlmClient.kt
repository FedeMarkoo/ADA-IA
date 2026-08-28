package com.ada.conversation.application.port.out

import com.ada.dto.LlmRequest

interface LlmClient { fun complete(request: LlmRequest): LlmCompletion }
