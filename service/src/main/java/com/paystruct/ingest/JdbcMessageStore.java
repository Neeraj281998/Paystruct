package com.paystruct.ingest;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/**
 * Postgres storage. Message and address columns are exactly those in the spec. What the spec tables have no
 * column for goes in two places (see docs/decisions/ingest-persistence.md):
 * addresses.evidence.ingest holds xmlPath, countryHint, alreadyStructured, existing fields and the document-order
 * ordinal; message_ingest_reports holds the schema errors.
 */
@Repository
public class JdbcMessageStore implements MessageStore {

    static final String STATUS_RECEIVED = "RECEIVED";

    private static final TypeReference<List<String>> STRINGS = new TypeReference<>() {};
    private static final TypeReference<List<SchemaError>> ERRORS = new TypeReference<>() {};

    private final JdbcTemplate jdbc;
    private final ObjectMapper json;

    public JdbcMessageStore(JdbcTemplate jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    @Override
    public Optional<MessageReport> findByHash(String contentHash) {
        List<UUID> ids = jdbc.queryForList("SELECT id FROM messages WHERE content_hash = ?", UUID.class, contentHash);
        return ids.isEmpty() ? Optional.empty() : findById(ids.get(0));
    }

    @Override
    public Optional<MessageReport> findById(UUID messageId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT message_type, status, input_valid FROM messages WHERE id = ?", messageId);
        if (rows.isEmpty()) {
            return Optional.empty();
        }
        Map<String, Object> m = rows.get(0);
        String messageType = (String) m.get("message_type");

        Map<String, Object> report = jdbc.queryForMap(
                "SELECT schema_error_count, schema_errors::text AS schema_errors FROM message_ingest_reports WHERE message_id = ?",
                messageId);
        List<SchemaError> errors = read((String) report.get("schema_errors"), ERRORS);

        List<AddressJob> jobs = jdbc.query(
                "SELECT id, party_role, raw_lines::text AS raw_lines, evidence::text AS evidence FROM addresses "
                        + "WHERE message_id = ? ORDER BY (evidence->'ingest'->>'ordinal')::int",
                (rs, i) -> {
                    JsonNode ingest = readTree(rs.getString("evidence")).get("ingest");
                    JsonNode hint = ingest.get("countryHint");
                    return new AddressJob(
                            rs.getObject("id", UUID.class),
                            messageId,
                            messageType,
                            PartyRole.valueOf(rs.getString("party_role")),
                            ingest.get("xmlPath").asText(),
                            read(rs.getString("raw_lines"), STRINGS),
                            json.convertValue(ingest.get("existing"), StructuredAddress.class),
                            hint == null || hint.isNull() ? null : hint.asText(),
                            ingest.get("alreadyStructured").asBoolean());
                },
                messageId);

        return Optional.of(new MessageReport(
                messageId,
                messageType,
                (String) m.get("status"),
                Boolean.TRUE.equals(m.get("input_valid")),
                ((Number) report.get("schema_error_count")).intValue(),
                errors,
                false,
                jobs));
    }

    @Override
    @Transactional
    public boolean save(UUID messageId, String contentHash, String messageType, SchemaValidation validation, List<AddressJob> jobs) {
        int inserted = jdbc.update(
                "INSERT INTO messages (id, content_hash, message_type, status, input_valid) VALUES (?, ?, ?, ?, ?) "
                        + "ON CONFLICT (content_hash) DO NOTHING",
                messageId, contentHash, messageType, STATUS_RECEIVED, validation.valid());
        if (inserted == 0) {
            return false;
        }
        jdbc.update(
                "INSERT INTO message_ingest_reports (message_id, schema_error_count, schema_errors) VALUES (?, ?, ?::jsonb)",
                messageId, validation.errorCount(), write(validation.errors()));
        int ordinal = 0;
        for (AddressJob job : jobs) {
            ObjectNode ingest = json.createObjectNode();
            ingest.put("ordinal", ordinal++);
            ingest.put("xmlPath", job.xmlPath());
            ingest.put("countryHint", job.countryHint());
            ingest.put("alreadyStructured", job.alreadyStructured());
            ingest.set("existing", json.valueToTree(job.existing()));
            ObjectNode evidence = json.createObjectNode();
            evidence.set("ingest", ingest);
            jdbc.update(
                    "INSERT INTO addresses (id, message_id, party_role, raw_lines, evidence) VALUES (?, ?, ?, ?::jsonb, ?::jsonb)",
                    job.jobId(), messageId, job.role().name(), write(job.rawLines()), write(evidence));
        }
        return true;
    }

    private String write(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }

    private JsonNode readTree(String text) {
        try {
            return json.readTree(text);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }

    private <T> T read(String text, TypeReference<T> type) {
        try {
            return json.readValue(text, type);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException(e);
        }
    }
}
