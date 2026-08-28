package com.ada.conversation.adapters.`in`

import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController

@RestController
class HealthController {
    @GetMapping("/api/v1/ping")
    fun ping(): Map<String, String> = mapOf("status" to "ok")
}
