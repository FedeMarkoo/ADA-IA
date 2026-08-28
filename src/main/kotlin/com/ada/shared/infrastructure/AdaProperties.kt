package com.ada.shared.infrastructure

import com.ada.dto.LlmProperties
import jakarta.validation.constraints.NotBlank
import org.springframework.boot.context.properties.ConfigurationProperties
import org.springframework.validation.annotation.Validated
import java.nio.file.Path

@Validated
@ConfigurationProperties(prefix = "ada")
class AdaProperties(
    @field:NotBlank val dataDir: String,
    val llm: LlmProperties,
) {
    val normalizedDataDirectory: Path get() = Path.of(dataDir).toAbsolutePath().normalize()
}
