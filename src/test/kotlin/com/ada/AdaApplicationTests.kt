package com.ada

import org.junit.jupiter.api.Test
import org.springframework.boot.test.context.SpringBootTest

@SpringBootTest(properties = ["ada.data-dir=target/test-data/application-context"])
class AdaApplicationTests {
    @Test
    fun contextLoads() {
    }
}
