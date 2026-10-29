package com.paystruct.config;

import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;

/**
 * Fails startup, before any datasource or Flyway bean exists, if a datasource setting still contains an unresolved
 * placeholder. Without this the literal text "${POSTGRES_USER}" can end up as the database user name, and the only
 * symptom is a confusing "password authentication failed" from Postgres.
 */
public class DatasourceSettingsCheck implements EnvironmentPostProcessor, Ordered {

    static final List<String> SETTINGS = List.of("spring.datasource.url", "spring.datasource.username", "spring.datasource.password");

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        List<String> problems = new ArrayList<>();
        for (String name : SETTINGS) {
            String value;
            try {
                value = environment.getProperty(name);
            } catch (IllegalArgumentException e) { // Spring's own "Could not resolve placeholder"
                problems.add(name + " refers to a placeholder that has no value (" + e.getMessage() + ")");
                continue;
            }
            if (value != null && value.contains("${")) {
                // The value is deliberately not echoed in full: it might sit next to a real password.
                problems.add(name + " still contains an unresolved ${...} placeholder");
            }
        }
        if (!problems.isEmpty()) {
            throw new IllegalStateException("Datasource configuration is not usable:\n  - " + String.join("\n  - ", problems)
                    + "\nSet the missing POSTGRES_* environment variables (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,"
                    + " POSTGRES_USER, POSTGRES_PASSWORD), or fix spring.datasource.* in application.yml."
                    + " For the local database run `docker compose up -d` from the repository root; see the README.");
        }
    }

    @Override
    public int getOrder() {
        return Ordered.LOWEST_PRECEDENCE; // after application.yml and environment variables are loaded
    }
}
