package com.paystruct.ingest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class MessageTypeDetectorTest {

    private final MessageTypeDetector detector = new MessageTypeDetector(TestSupport.registry());

    @Test
    void detectsPacs008FromTheNamespace() {
        MessageType type = detector.detect(TestSupport.sampleFile("pacs008-unstructured.xml"));
        assertThat(type.type()).isEqualTo("pacs.008");
        assertThat(type.namespace()).isEqualTo("urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14");
    }

    @Test
    void detectsPain001FromTheNamespace() {
        assertThat(detector.detect(TestSupport.sampleFile("pain001-unstructured.xml")).type()).isEqualTo("pain.001");
    }

    @Test
    void rejectsAnUnknownNamespaceWithAClearError() {
        var file = TestSupport.file("<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:camt.053.001.13\"/>");
        assertThatThrownBy(() -> detector.detect(file))
                .isInstanceOfSatisfying(IngestException.class, e -> {
                    assertThat(e.status()).isEqualTo(HttpStatus.BAD_REQUEST);
                    assertThat(e.code()).isEqualTo("UNSUPPORTED_MESSAGE_TYPE");
                    assertThat(e.getMessage())
                            .contains("camt.053.001.13")
                            .contains("pacs.008.001.14")
                            .contains("pain.001.001.13");
                });
    }

    @Test
    void rejectsARootWithNoNamespace() {
        var file = TestSupport.file("<Document><x/></Document>");
        assertThatThrownBy(() -> detector.detect(file))
                .isInstanceOfSatisfying(IngestException.class, e -> {
                    assertThat(e.code()).isEqualTo("UNSUPPORTED_MESSAGE_TYPE");
                    assertThat(e.getMessage()).contains("no namespace");
                });
    }

    @Test
    void rejectsTextThatIsNotXml() {
        var file = TestSupport.file("this is not xml");
        assertThatThrownBy(() -> detector.detect(file))
                .isInstanceOfSatisfying(IngestException.class, e -> {
                    assertThat(e.status()).isEqualTo(HttpStatus.BAD_REQUEST);
                    assertThat(e.code()).isEqualTo("MALFORMED_XML");
                });
    }

    @Test
    void rejectsADoctype() {
        var file = TestSupport.file("<!DOCTYPE Document []><Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14\"/>");
        assertThatThrownBy(() -> detector.detect(file))
                .isInstanceOfSatisfying(IngestException.class, e -> assertThat(e.code()).isEqualTo("DTD_NOT_ALLOWED"));
    }

    @Test
    void supportedNamespacesComeFromConfigurationOnly() {
        // A registry configured with pacs.008 alone rejects pain.001: no code names the supported versions.
        var onlyPacs = new MessageTypeDetector(new MessageTypeRegistry(TestSupport.properties(10, TestSupport.PACS008)));
        assertThat(onlyPacs.detect(TestSupport.sampleFile("pacs008-unstructured.xml")).type()).isEqualTo("pacs.008");
        var pain = TestSupport.sampleFile("pain001-unstructured.xml");
        assertThatThrownBy(() -> onlyPacs.detect(pain))
                .isInstanceOfSatisfying(IngestException.class, e -> assertThat(e.code()).isEqualTo("UNSUPPORTED_MESSAGE_TYPE"));
    }
}
