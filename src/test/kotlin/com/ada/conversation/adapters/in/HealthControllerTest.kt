package com.ada.conversation.infrastructure.in.rest

import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.get
import org.springframework.test.web.servlet.post

@WebMvcTest(controllers = [HealthController::class])
class HealthControllerTest {
    @Autowired
    private lateinit var mockMvc: MockMvc

    @Test
    fun `ping reports an ok status as json`() {
        mockMvc.get("/api/v1/ping")
            .andExpect {
                status { isOk() }
                content { contentType(MediaType.APPLICATION_JSON) }
                jsonPath("$.status") { value("ok") }
            }
    }

    @Test
    fun `ping rejects unsupported http methods`() {
        mockMvc.post("/api/v1/ping")
            .andExpect {
                status { isMethodNotAllowed() }
            }
    }
}
