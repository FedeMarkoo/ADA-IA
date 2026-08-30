package com.ada.autonomy.infrastructure.in;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Getter
@Setter
@NoArgsConstructor
@ConfigurationProperties(prefix = "ada.autonomy")
public class AutonomyProperties {
  private Scheduler scheduler = new Scheduler();
  private Weather weather = new Weather();

  @Getter
  @Setter
  public static class Scheduler {
    private long pollMs = 30000;
  }

  @Getter
  @Setter
  public static class Weather {
    private boolean enabled;
    private String timezone = "America/Argentina/Buenos_Aires";
    private String cron = "0 0 8 * * *";
    private String location = "";
    private String conversationId = "autonomy-weather";
    private String prompt = "";
  }
}
