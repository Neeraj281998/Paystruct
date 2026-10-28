package com.paystruct.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.paystruct.ingest.AddressJobExtractor;
import com.paystruct.ingest.IngestException;
import com.paystruct.ingest.IngestProperties;
import com.paystruct.ingest.IngestionService;
import com.paystruct.ingest.MessageAnalyzer;
import com.paystruct.ingest.MessageTypeDetector;
import com.paystruct.ingest.MessageTypeRegistry;
import com.paystruct.ingest.SchemaValidator;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/**
 * The refusals that protect the service, exercised through the real controller, parser and validator with an
 * in-memory store: XXE payloads and oversized bodies are rejected and nothing is stored. No database needed.
 */
@WebMvcTest(MessageController.class)
@Import({MessageTypeRegistry.class, MessageTypeDetector.class, SchemaValidator.class, AddressJobExtractor.class,
        MessageAnalyzer.class, IngestionService.class, MessageApiSecurityTest.Config.class})
@EnableConfigurationProperties(IngestProperties.class)
class MessageApiSecurityTest {

    @TestConfiguration
    static class Config {
        @Bean
        InMemoryMessageStore messageStore() {
            return new InMemoryMessageStore();
        }
    }

    @Autowired MockMvc mvc;
    @Autowired InMemoryMessageStore store;
    @Autowired IngestionService ingestion;

    @BeforeEach
    void emptyStore() {
        store.byHash.clear(); // the store is a singleton shared by every test in this class
    }

    private static byte[] sample(String name) throws IOException {
        try (InputStream in = new ClassPathResource("samples/" + name).getInputStream()) {
            return in.readAllBytes();
        }
    }

    @Test
    void xxePayloadIsRejectedAndNothingIsResolvedOrStored() throws Exception {
        MvcResult result = mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(sample("xxe-payload.xml")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("DTD_NOT_ALLOWED"))
                .andReturn();
        String body = result.getResponse().getContentAsString();
        assertThat(body).doesNotContain("root:").doesNotContain("/bin/").doesNotContain("nobody");
        assertThat(store.byHash).isEmpty();
    }

    @Test
    void oversizedBodyIsRejectedWithPayloadTooLarge() throws Exception {
        byte[] huge = new byte[5 * 1024 * 1024 + 1];
        Arrays.fill(huge, (byte) 'a');
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(huge))
                .andExpect(status().isPayloadTooLarge())
                .andExpect(jsonPath("$.error").value("PAYLOAD_TOO_LARGE"));
        assertThat(store.byHash).isEmpty();
    }

    @Test
    void bodyOverTheCapIsRejectedEvenWhenNoContentLengthIsDeclared() {
        // A chunked upload declares no length, so the cap must hold on the bytes actually read.
        InputStream endless = new InputStream() {
            @Override
            public int read() {
                return 'a';
            }

            @Override
            public int read(byte[] b, int off, int len) {
                Arrays.fill(b, off, off + len, (byte) 'a');
                return len;
            }
        };
        assertThatThrownBy(() -> ingestion.ingest(endless, -1))
                .isInstanceOfSatisfying(IngestException.class, e -> assertThat(e.code()).isEqualTo("PAYLOAD_TOO_LARGE"));
        assertThat(store.byHash).isEmpty();
    }

    @Test
    void bodyAtExactlyTheCapIsNotRejectedForSize() {
        // 5 MiB of padding inside a comment is within the cap; it fails later for being malformed, not for size.
        String xml = "<!-- " + "a".repeat(5 * 1024 * 1024 - 100) + " --><x/>";
        byte[] body = xml.getBytes(StandardCharsets.UTF_8);
        assertThat(body.length).isLessThanOrEqualTo(5 * 1024 * 1024);
        assertThatThrownBy(() -> ingestion.ingest(new ByteArrayInputStream(body), body.length))
                .isInstanceOfSatisfying(IngestException.class, e -> assertThat(e.code()).isEqualTo("UNSUPPORTED_MESSAGE_TYPE"));
    }

    @Test
    void entityReferenceWithoutADoctypeIsRejected() throws Exception {
        String xml = "<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14\">&xxe;</Document>";
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(xml))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("MALFORMED_XML"));
        assertThat(store.byHash).isEmpty();
    }

    @Test
    void unknownMessageTypeIsRejectedWithAClearBody() throws Exception {
        String xml = "<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:camt.053.001.13\"/>";
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(xml))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("UNSUPPORTED_MESSAGE_TYPE"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("camt.053.001.13")));
        assertThat(store.byHash).isEmpty();
    }

    @Test
    void emptyBodyIsRejected() throws Exception {
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(new byte[0]))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("EMPTY_BODY"));
    }

    @Test
    void nonXmlContentTypeIsRejected() throws Exception {
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.error").value("UNSUPPORTED_MEDIA_TYPE"));
    }

    @Test
    void validMessageIsAcceptedAndASecondIdenticalPostIsADuplicate() throws Exception {
        byte[] xml = sample("pacs008-unstructured.xml");
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(xml))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.duplicate").value(false))
                .andExpect(jsonPath("$.inputValid").value(true))
                .andExpect(jsonPath("$.addressJobs.length()").value(3));
        mvc.perform(post("/v1/messages").contentType(MediaType.APPLICATION_XML).content(xml))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.duplicate").value(true));
        assertThat(store.byHash).hasSize(1);
    }

    @Test
    void getUnknownIdIs404AndMalformedIdIs400() throws Exception {
        mvc.perform(get("/v1/messages/00000000-0000-0000-0000-000000000000"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("MESSAGE_NOT_FOUND"));
        mvc.perform(get("/v1/messages/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_ID"));
    }
}
