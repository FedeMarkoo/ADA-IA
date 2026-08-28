package com.ada;

import org.springframework.boot.SpringApplication; import org.springframework.boot.autoconfigure.SpringBootApplication; import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
@SpringBootApplication @ConfigurationPropertiesScan public class AdaApplication { public static void main(String[] args){SpringApplication.run(AdaApplication.class,args);} }
