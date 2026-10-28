package com.paystruct.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * The whole ingestion path against real PostgreSQL 16 (the same pgvector image Docker Compose uses), with the
 * real Flyway migrations. Needs Docker; runs under `./mvnw verify`.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class MessageIngestionIT {

    @Container
    @ServiceConnection
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;

    @BeforeEach
    void cleanTables() {
        jdbc.update("DELETE FROM review_items");
        jdbc.update("DELETE FROM message_ingest_reports");
        jdbc.update("DELETE FROM addresses");
        jdbc.update("DELETE FROM messages");
    }

    private static byte[] sample(String name) throws IOException {
        try (InputStream in = new ClassPathResource("samples/" + name).getInputStream()) {
            return in.readAllBytes();
        }
    }

    private JsonNode postSample(String sample) throws Exception {
        String body = mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(sample(sample)))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        return json.readTree(body);
    }

    @Test
    void migrationsCreateTheSpecTablesAndNotRuleCards() {
        List<String> tables = jdbc.queryForList(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", String.class);
        assertThat(tables).contains("messages", "addresses", "review_items", "eval_runs", "message_ingest_reports");
        assertThat(tables).doesNotContain("rule_cards"); // Phase 7
    }

    @Test
    void messagesTableMatchesTheSpecColumns() {
        List<String> columns = jdbc.queryForList(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'messages' ORDER BY ordinal_position", String.class);
        assertThat(columns).containsExactly("id", "content_hash", "message_type", "status", "input_valid", "received_at");
        List<String> addresses = jdbc.queryForList(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'addresses' ORDER BY ordinal_position", String.class);
        assertThat(addresses).containsExactly("id", "message_id", "party_role", "raw_lines", "result", "evidence",
                "method", "confidence", "latency_ms", "llm_cost_usd");
    }

    @Test
    void firstPostStoresTheMessageAndItsJobs() throws Exception {
        JsonNode first = postSample("pacs008-unstructured.xml");
        assertThat(first.get("duplicate").asBoolean()).isFalse();
        assertThat(first.get("messageType").asText()).isEqualTo("pacs.008");
        assertThat(first.get("inputValid").asBoolean()).isTrue();
        assertThat(first.get("addressJobs")).hasSize(3);

        assertThat(jdbc.queryForObject("SELECT count(*) FROM messages", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM addresses", Integer.class)).isEqualTo(3);
        assertThat(jdbc.queryForObject("SELECT content_hash FROM messages", String.class)).hasSize(64).matches("[0-9a-f]{64}");
        assertThat(jdbc.queryForObject("SELECT status FROM messages", String.class)).isEqualTo("RECEIVED");
    }

    @Test
    void theSameMessageAgainReturnsTheStoredResultAndIsMarkedDuplicate() throws Exception {
        JsonNode first = postSample("pacs008-unstructured.xml");
        JsonNode second = postSample("pacs008-unstructured.xml");

        assertThat(second.get("duplicate").asBoolean()).isTrue();
        assertThat(second.get("messageId")).isEqualTo(first.get("messageId"));
        // The stored result, not a recomputed one: same job ids, in the same order.
        assertThat(second.get("addressJobs")).isEqualTo(first.get("addressJobs"));
        assertThat(jdbc.queryForObject("SELECT count(*) FROM messages", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT count(*) FROM addresses", Integer.class)).isEqualTo(3);
    }

    @Test
    void differentMessagesAreNotDuplicates() throws Exception {
        JsonNode a = postSample("pacs008-unstructured.xml");
        JsonNode b = postSample("pacs008-structured.xml");
        assertThat(b.get("duplicate").asBoolean()).isFalse();
        assertThat(b.get("messageId")).isNotEqualTo(a.get("messageId"));
        assertThat(jdbc.queryForObject("SELECT count(*) FROM messages", Integer.class)).isEqualTo(2);
    }

    @Test
    void getReturnsWhatPostReturnedExceptTheDuplicateFlag() throws Exception {
        JsonNode posted = postSample("pain001-unstructured.xml");
        String id = posted.get("messageId").asText();
        mvc.perform(get("/v1/messages/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.messageId").value(id))
                .andExpect(jsonPath("$.messageType").value("pain.001"))
                .andExpect(jsonPath("$.status").value("RECEIVED"))
                .andExpect(jsonPath("$.duplicate").value(false))
                .andExpect(jsonPath("$.addressJobs.length()").value(3));
        JsonNode got = json.readTree(mvc.perform(get("/v1/messages/" + id)).andReturn().getResponse().getContentAsString());
        assertThat(got.get("addressJobs")).isEqualTo(posted.get("addressJobs"));
    }

    @Test
    void alreadyStructuredAddressesAreMarkedAndTheirFieldsSurviveTheRoundTrip() throws Exception {
        JsonNode posted = postSample("pacs008-structured.xml");
        JsonNode got = json.readTree(mvc.perform(get("/v1/messages/" + posted.get("messageId").asText()))
                .andReturn().getResponse().getContentAsString());
        for (JsonNode job : got.get("addressJobs")) {
            assertThat(job.get("alreadyStructured").asBoolean()).isTrue();
            assertThat(job.get("existing").get("TwnNm").asText()).isNotBlank();
        }
        assertThat(got.get("addressJobs").get(1).get("existing").get("AdrTp").asText()).isEqualTo("BIZZ");
        assertThat(got.get("addressJobs").get(0).get("countryHint").asText()).isEqualTo("DE");
    }

    @Test
    void rejectedMessagesStoreNothing() throws Exception {
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(sample("xxe-payload.xml")))
                .andExpect(status().isBadRequest());
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML)
                        .content("<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:camt.053.001.13\"/>"))
                .andExpect(status().isBadRequest());
        assertThat(jdbc.queryForObject("SELECT count(*) FROM messages", Integer.class)).isZero();
        assertThat(jdbc.queryForObject("SELECT count(*) FROM addresses", Integer.class)).isZero();
    }

    @Test
    void schemaErrorsAreStoredAndReturnedOnDuplicate() throws Exception {
        String invalid = new String(sample("pacs008-unstructured.xml"), java.nio.charset.StandardCharsets.UTF_8)
                .replace("<AdrLine>Riverside Road</AdrLine>", "<AdrLine>Riverside Road</AdrLine><Ctry>ie</Ctry>");
        // Ctry after AdrLine breaks the sequence order and the country pattern: bad input is still processed.
        String body = mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(invalid))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        JsonNode first = json.readTree(body);
        assertThat(first.get("inputValid").asBoolean()).isFalse();
        assertThat(first.get("schemaErrorCount").asInt()).isPositive();
        assertThat(first.get("schemaErrors")).isNotEmpty();
        assertThat(first.get("addressJobs")).hasSize(3); // still extracted

        String again = mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(invalid))
                .andReturn().getResponse().getContentAsString();
        JsonNode second = json.readTree(again);
        assertThat(second.get("duplicate").asBoolean()).isTrue();
        assertThat(second.get("schemaErrors")).isEqualTo(first.get("schemaErrors"));
        assertThat(second.get("inputValid").asBoolean()).isFalse();
    }
}
