package com.ada.shared.infrastructure;

import com.ada.shared.infrastructure.dto.LlmProperties; import jakarta.validation.constraints.NotBlank; import org.springframework.boot.context.properties.ConfigurationProperties; import org.springframework.validation.annotation.Validated; import java.nio.file.*;
@Validated @ConfigurationProperties(prefix="ada") public class AdaProperties { @NotBlank private final String dataDir; private final LlmProperties llm; public AdaProperties(String d,LlmProperties l){dataDir=d;llm=l;} public String getDataDir(){return dataDir;} public LlmProperties getLlm(){return llm;} public Path getNormalizedDataDirectory(){return Path.of(dataDir).toAbsolutePath().normalize();} }
