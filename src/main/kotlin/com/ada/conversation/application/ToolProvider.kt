package com.ada.conversation.application

import com.ada.conversation.application.dto.LlmTool

interface ToolProvider { fun tools(): List<LlmTool> }
