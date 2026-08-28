package com.ada.shared.infrastructure

import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.sqlite.SQLiteDataSource
import javax.sql.DataSource

@Configuration(proxyBeanMethods = false)
class DataSourceConfiguration {
    @Bean
    fun dataSource(properties: AdaProperties): DataSource = SQLiteDataSource().apply {
        url = "jdbc:sqlite:${properties.normalizedDataDirectory.resolve("db/ada.sqlite")}"
    }
}
