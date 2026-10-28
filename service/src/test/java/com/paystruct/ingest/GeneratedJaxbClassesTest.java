package com.paystruct.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.xml.bind.JAXBContext;
import jakarta.xml.bind.JAXBElement;
import jakarta.xml.bind.Unmarshaller;
import java.io.ByteArrayInputStream;
import org.junit.jupiter.api.Test;

/**
 * The classes xjc generates from the XSDs (jakarta namespace) read the sample messages, and the address fields
 * line up with what the ingestion extractor reports. Guards against the generated code and the XSD drifting apart.
 */
class GeneratedJaxbClassesTest {

    @Test
    void pacs008ClassesReadTheStructuredSample() throws Exception {
        Unmarshaller u = JAXBContext.newInstance(com.paystruct.xml.pacs008.Document.class).createUnmarshaller();
        var doc = u.unmarshal(new javax.xml.transform.stream.StreamSource(
                new ByteArrayInputStream(TestSupport.sample("pacs008-structured.xml"))), com.paystruct.xml.pacs008.Document.class);
        com.paystruct.xml.pacs008.Document d = ((JAXBElement<com.paystruct.xml.pacs008.Document>) doc).getValue();
        var tx = d.getFIToFICstmrCdtTrf().getCdtTrfTxInf().get(0);
        var address = tx.getDbtr().getPstlAdr();
        assertThat(address.getTwnNm()).isEqualTo("Hamburg");
        assertThat(address.getCtry()).isEqualTo("DE");
        assertThat(address.getAdrLine()).isEmpty();
    }

    @Test
    void pain001ClassesReadTheUnstructuredSample() throws Exception {
        Unmarshaller u = JAXBContext.newInstance(com.paystruct.xml.pain001.Document.class).createUnmarshaller();
        var doc = u.unmarshal(new javax.xml.transform.stream.StreamSource(
                new ByteArrayInputStream(TestSupport.sample("pain001-unstructured.xml"))), com.paystruct.xml.pain001.Document.class);
        com.paystruct.xml.pain001.Document d = ((JAXBElement<com.paystruct.xml.pain001.Document>) doc).getValue();
        var address = d.getCstmrCdtTrfInitn().getPmtInf().get(0).getDbtr().getPstlAdr();
        assertThat(address.getAdrLine()).containsExactly("7 Orchard Lane", "Cork T12 XY34", "IRELAND");
    }
}
