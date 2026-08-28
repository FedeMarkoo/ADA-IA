package com.ada.shared.infrastructure

import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.sqlite.SQLiteDataSource
import javax.sql.DataSource
import java.nio.file.Files

@Configuration(proxyBeanMethods = false)
class DataSourceConfiguration {
    @Bean
    fun dataSource(properties: AdaProperties): DataSource {
        val databaseDirectory = properties.normalizedDataDirectory.resolve("db")
        Files.createDirectories(databaseDirectory)
        return SQLiteDataSource().apply {
            url = "jdbc:sqlite:${databaseDirectory.resolve("ada.sqlite")}"
        }
    }
}
