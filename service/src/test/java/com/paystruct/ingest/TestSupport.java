package com.paystruct.ingest;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.springframework.core.io.ClassPathResource;
import org.springframework.util.unit.DataSize;

/** Builds the ingestion components by hand, with the same message types as application.yml, no Spring needed. */
final class TestSupport {

    static final IngestProperties.MessageTypeConfig PACS008 = new IngestProperties.MessageTypeConfig(
            "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14", "pacs.008", "xsd/pacs.008.001.14.xsd");
    static final IngestProperties.MessageTypeConfig PAIN001 = new IngestProperties.MessageTypeConfig(
            "urn:iso:std:iso:20022:tech:xsd:pain.001.001.13", "pain.001", "xsd/pain.001.001.13.xsd");

    private TestSupport() {}

    static IngestProperties properties(int maxSchemaErrors, IngestProperties.MessageTypeConfig... types) {
        return new IngestProperties(DataSize.ofMegabytes(5), maxSchemaErrors, List.of(types));
    }

    static IngestProperties properties() {
        return properties(1000, PACS008, PAIN001);
    }

    static MessageTypeRegistry registry() {
        return new MessageTypeRegistry(properties());
    }

    static MessageAnalyzer analyzer() {
        IngestProperties props = properties();
        return new MessageAnalyzer(
                new MessageTypeDetector(new MessageTypeRegistry(props)),
                new SchemaValidator(props),
                new AddressJobExtractor());
    }

    static byte[] sample(String name) {
        try (InputStream in = new ClassPathResource("samples/" + name).getInputStream()) {
            return in.readAllBytes();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Writes XML text to a temp file; the JVM deletes it on exit. */
    static Path file(String xml) {
        try {
            Path p = Files.createTempFile("paystruct-test-", ".xml");
            p.toFile().deleteOnExit();
            Files.writeString(p, xml, StandardCharsets.UTF_8);
            return p;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    static Path sampleFile(String name) {
        try {
            Path p = Files.createTempFile("paystruct-sample-", ".xml");
            p.toFile().deleteOnExit();
            Files.write(p, sample(name));
            return p;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }
}
