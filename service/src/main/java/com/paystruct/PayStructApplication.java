package com.paystruct;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class PayStructApplication {
    public static void main(String[] args) {
        SpringApplication.run(PayStructApplication.class, args);
    }
}
