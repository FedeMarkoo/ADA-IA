package com.ada.shared.infrastructure;

import java.nio.file.*;
import javax.sql.DataSource;
import org.springframework.context.annotation.*;
import org.sqlite.SQLiteDataSource;

@Configuration(proxyBeanMethods = false)
public class DataSourceConfiguration {
  @Bean
  public DataSource dataSource(AdaProperties p) throws Exception {
    Path d = p.getNormalizedDataDirectory().resolve("db");
    Files.createDirectories(d);
    var ds = new SQLiteDataSource();
    ds.setUrl("jdbc:sqlite:" + d.resolve("ada.sqlite"));
    return ds;
  }
}
