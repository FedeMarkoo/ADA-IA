package com.ada.shared.infrastructure;

import org.springframework.context.annotation.*; import org.sqlite.SQLiteDataSource; import javax.sql.DataSource; import java.nio.file.*;
@Configuration(proxyBeanMethods=false) public class DataSourceConfiguration { @Bean DataSource dataSource(AdaProperties p)throws Exception{Path d=p.getNormalizedDataDirectory().resolve("db");Files.createDirectories(d);var ds=new SQLiteDataSource();ds.setUrl("jdbc:sqlite:"+d.resolve("ada.sqlite"));return ds;} }
