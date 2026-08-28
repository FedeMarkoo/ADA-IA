package com.ada.conversation.infrastructure.in.rest

import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController

@RestController
class HealthController {
    /**
     * Reports the service health status.
     *
     * @return A map containing the status value `"ok"`.
     */
    @GetMapping("/api/v1/ping")
    fun ping(): Map<String, String> = mapOf("status" to "ok")
}
