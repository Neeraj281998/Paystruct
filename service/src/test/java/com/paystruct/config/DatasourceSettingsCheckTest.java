package com.paystruct.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.paystruct.PayStructApplication;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;

class DatasourceSettingsCheckTest {

    private final DatasourceSettingsCheck check = new DatasourceSettingsCheck();

    private StandardEnvironment env(Map<String, Object> properties) {
        StandardEnvironment env = new StandardEnvironment();
        env.getPropertySources().addFirst(new MapPropertySource("test", properties));
        return env;
    }

    @Test
    void resolvedSettingsPass() {
        var env = env(Map.of("spring.datasource.url", "jdbc:postgresql://localhost:5432/paystruct",
                "spring.datasource.username", "paystruct", "spring.datasource.password", "x"));
        assertThatCode(() -> check.postProcessEnvironment(env, null)).doesNotThrowAnyException();
    }

    @Test
    void aPlaceholderWithADefaultResolvesAndPasses() {
        var env = env(Map.of("spring.datasource.url", "jdbc:postgresql://localhost/${NOT_SET_ANYWHERE:paystruct}",
                "spring.datasource.username", "${ALSO_NOT_SET:paystruct}", "spring.datasource.password", "${NOR_THIS:paystruct}"));
        assertThatCode(() -> check.postProcessEnvironment(env, null)).doesNotThrowAnyException();
    }

    @Test
    void anUnresolvedPlaceholderFailsWithAClearMessage() {
        var env = env(Map.of("spring.datasource.url", "jdbc:postgresql://localhost/paystruct",
                "spring.datasource.username", "${POSTGRES_USER_THAT_IS_NOT_SET}", "spring.datasource.password", "x"));
        assertThatThrownBy(() -> check.postProcessEnvironment(env, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Datasource configuration is not usable")
                .hasMessageContaining("spring.datasource.username")
                .hasMessageContaining("POSTGRES_USER")
                .hasMessageContaining("docker compose up -d");
    }

    @Test
    void everyUnresolvedSettingIsReportedNotJustTheFirst() {
        var env = env(Map.of("spring.datasource.url", "jdbc:postgresql://localhost/${NOPE_DB}",
                "spring.datasource.username", "${NOPE_USER}", "spring.datasource.password", "${NOPE_PASSWORD}"));
        assertThatThrownBy(() -> check.postProcessEnvironment(env, null))
                .hasMessageContaining("spring.datasource.url")
                .hasMessageContaining("spring.datasource.username")
                .hasMessageContaining("spring.datasource.password");
    }

    @Test
    void theCheckIsWiredIntoStartupAndStopsTheApplicationBeforeAnyDatabaseConnection() {
        // A command-line argument outranks application.yml (builder .properties() would not). The failure must be the
        // check's own message, before Flyway or a connection pool exists; if the check were not registered, startup
        // would fail later with a database error instead.
        assertThatThrownBy(() -> new SpringApplicationBuilder(PayStructApplication.class)
                .web(WebApplicationType.NONE)
                .run("--spring.datasource.username=${POSTGRES_USER_THAT_IS_NOT_SET}"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Datasource configuration is not usable")
                .hasMessageContaining("spring.datasource.username");
    }

    @Test
    void theApplicationYmlDefaultsSatisfyTheCheckWithNoEnvironmentVariables() {
        var env = new StandardEnvironment();
        new org.springframework.boot.context.config.ConfigDataEnvironmentPostProcessor(
                new org.springframework.boot.logging.DeferredLogFactory() {
                    @Override
                    public org.apache.commons.logging.Log getLog(java.util.function.Supplier<org.apache.commons.logging.Log> destination) {
                        return destination.get();
                    }
                }, new org.springframework.boot.DefaultBootstrapContext()).postProcessEnvironment(env, new org.springframework.boot.SpringApplication());
        assertThatCode(() -> check.postProcessEnvironment(env, null)).doesNotThrowAnyException();
        assertThat(env.getProperty("spring.datasource.url")).isNotNull();
    }
}
