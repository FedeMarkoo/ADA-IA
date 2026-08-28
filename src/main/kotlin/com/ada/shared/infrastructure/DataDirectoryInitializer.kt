package com.ada.shared.infrastructure

import org.springframework.boot.ApplicationRunner
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import java.nio.file.Files

@Configuration
class DataDirectoryInitializer(
    private val properties: AdaProperties,
) {
    /**
     * Creates an application runner that initializes the required data subdirectories at startup.
     *
     * @return An application runner that creates the `db`, `logs`, `backups`, `exports`, `models`, and `runtime` directories.
     */
    @Bean
    fun initializeDataDirectory(): ApplicationRunner = ApplicationRunner {
        val dataDirectory = properties.normalizedDataDirectory
        listOf("db", "logs", "backups", "exports", "models", "runtime")
            .map(dataDirectory::resolve)
            .forEach(Files::createDirectories)
    }
}
