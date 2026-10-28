package com.paystruct.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * Known XML in, expected JSON report out, one golden file per sample. Random ids are blanked before comparing.
 * To regenerate after an intended change: ./mvnw test -Dtest=GoldenFileTest -Dgolden.update=true, then review the diff.
 */
class GoldenFileTest {

    private final ObjectMapper json = new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT);
    private final MessageAnalyzer analyzer = TestSupport.analyzer();

    @ParameterizedTest
    @ValueSource(strings = {"pacs008-unstructured", "pacs008-structured", "pain001-unstructured"})
    void reportMatchesTheGoldenFile(String sample) throws IOException {
        UUID messageId = UUID.randomUUID();
        Analysis a = analyzer.analyze(TestSupport.sampleFile(sample + ".xml"), messageId);
        MessageReport report = new MessageReport(messageId, a.type().type(), "RECEIVED", a.validation().valid(),
                a.validation().errorCount(), a.validation().errors(), false, a.jobs());
        JsonNode actual = normalise(json.valueToTree(report));

        Path golden = Path.of("src/test/resources/golden/" + sample + ".json");
        if (Boolean.getBoolean("golden.update")) {
            Files.writeString(golden, json.writeValueAsString(actual) + "\n");
        }
        assertThat(actual).isEqualTo(json.readTree(Files.readString(golden)));
    }

    private static JsonNode normalise(JsonNode report) {
        ObjectNode copy = ((ObjectNode) report).deepCopy();
        copy.put("messageId", "<id>");
        copy.withArray("addressJobs").forEach(job -> {
            ((ObjectNode) job).put("jobId", "<id>");
            ((ObjectNode) job).put("messageId", "<id>");
        });
        return copy;
    }
}
