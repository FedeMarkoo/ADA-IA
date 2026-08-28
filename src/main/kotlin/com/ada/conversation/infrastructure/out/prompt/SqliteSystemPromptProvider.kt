package com.ada.conversation.infrastructure.out.prompt

import com.ada.conversation.application.SystemPromptProvider
import org.springframework.jdbc.core.JdbcTemplate
import org.springframework.stereotype.Component

@Component
class SqliteSystemPromptProvider(
    private val jdbcTemplate: JdbcTemplate,
) : SystemPromptProvider {
    override fun content(): String = jdbcTemplate.query(
        """
        SELECT content
        FROM system_prompts
        WHERE active = 1
        ORDER BY version DESC
        LIMIT 1
        """.trimIndent(),
    ) { resultSet, _ -> resultSet.getString("content") }
        .firstOrNull()
        ?: error("No active system prompt configured in SQLite")
}
