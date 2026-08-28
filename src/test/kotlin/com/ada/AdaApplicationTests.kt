package com.ada

import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.get

@SpringBootTest(properties = ["ada.data-dir=target/test-data/application-context"])
@AutoConfigureMockMvc
class AdaApplicationTests {
    @Autowired
    private lateinit var mockMvc: MockMvc

    @Test
    fun contextLoads() {
    }

    @Test
    fun `ping endpoint is available from the application context`() {
        mockMvc.get("/api/v1/ping")
            .andExpect { status { isOk() } }
    }
}
