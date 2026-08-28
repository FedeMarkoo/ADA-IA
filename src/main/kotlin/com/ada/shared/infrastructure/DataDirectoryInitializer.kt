package com.ada.shared.infrastructure

import org.springframework.beans.factory.annotation.Value
import org.springframework.boot.ApplicationRunner
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import java.nio.file.Files
import java.nio.file.Path

@Configuration
open class DataDirectoryInitializer(
    @Value("\${ada.data-dir:../ada-data}") private val dataDirectory: String,
) {
    @Bean
    open fun initializeDataDirectory(): ApplicationRunner = ApplicationRunner {
        listOf("db", "logs", "backups", "exports", "models", "runtime")
            .map { Path.of(dataDirectory, it) }
            .forEach(Files::createDirectories)
    }
}
