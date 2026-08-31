package com.ada.autonomy.infrastructure.out;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import java.time.Instant;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class SqliteScheduledTriggerStore implements ScheduledTriggerStore {
  private final JdbcTemplate jdbc;

  @Override
  public List<ScheduledTrigger> findDue(Instant now) {
    return jdbc.query(
        "SELECT * FROM scheduled_triggers WHERE enabled = 1 AND next_run_at <= ? ORDER BY next_run_at",
        (rs, row) -> fromRow(rs),
        now.toString());
  }

  @Override
  public void markExecuted(long id, Instant executedAt, Instant nextRunAt) {
    jdbc.update(
        "UPDATE scheduled_triggers SET last_run_at = ?, next_run_at = ? WHERE id = ?",
        executedAt.toString(),
        nextRunAt.toString(),
        id);
  }

  @Override
  public void save(ScheduledTrigger trigger) {
    jdbc.update(
        "INSERT INTO scheduled_triggers(name, event_type, cron_expression, timezone, prompt, conversation_id, enabled, next_run_at, last_run_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            + "ON CONFLICT(name) DO UPDATE SET event_type = excluded.event_type, cron_expression = excluded.cron_expression, timezone = excluded.timezone, prompt = excluded.prompt, conversation_id = excluded.conversation_id, enabled = excluded.enabled, next_run_at = excluded.next_run_at",
        trigger.name(),
        trigger.eventType(),
        trigger.cronExpression(),
        trigger.timezone(),
        trigger.prompt(),
        trigger.conversationId(),
        trigger.enabled() ? 1 : 0,
        trigger.nextRunAt().toString(),
        trigger.lastRunAt() == null ? null : trigger.lastRunAt().toString());
  }

  @Override
  public List<ScheduledTrigger> findAll() {
    return jdbc.query("SELECT * FROM scheduled_triggers ORDER BY name", (rs, row) -> fromRow(rs));
  }

  private ScheduledTrigger fromRow(java.sql.ResultSet rs) throws java.sql.SQLException {
    var lastRun = rs.getString("last_run_at");
    return new ScheduledTrigger(
        rs.getLong("id"),
        rs.getString("name"),
        rs.getString("event_type"),
        rs.getString("cron_expression"),
        rs.getString("timezone"),
        rs.getString("prompt"),
        rs.getString("conversation_id"),
        rs.getBoolean("enabled"),
        Instant.parse(rs.getString("next_run_at")),
        lastRun == null ? null : Instant.parse(lastRun));
  }
}
