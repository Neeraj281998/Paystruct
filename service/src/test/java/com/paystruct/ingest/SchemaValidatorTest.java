package com.paystruct.ingest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class SchemaValidatorTest {

    private final MessageTypeRegistry registry = TestSupport.registry();
    private final SchemaValidator validator = new SchemaValidator(TestSupport.properties());

    private MessageType pacs() {
        return registry.byNamespace(TestSupport.PACS008.namespace()).orElseThrow();
    }

    @Test
    void allThreeValidSamplesPassTheirSchema() {
        assertThat(validator.validate(TestSupport.sampleFile("pacs008-unstructured.xml"), pacs()).valid()).isTrue();
        assertThat(validator.validate(TestSupport.sampleFile("pacs008-structured.xml"), pacs()).valid()).isTrue();
        MessageType pain = registry.byNamespace(TestSupport.PAIN001.namespace()).orElseThrow();
        assertThat(validator.validate(TestSupport.sampleFile("pain001-unstructured.xml"), pain).valid()).isTrue();
    }

    /** pacs.008 skeleton with the given Dbtr PstlAdr body. */
    private static String withAddress(String pstlAdrBody) {
        return """
                <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14"><FIToFICstmrCdtTrf>
                <GrpHdr><MsgId>M</MsgId><CreDtTm>2026-10-12T09:30:00Z</CreDtTm><NbOfTxs>1</NbOfTxs>
                <SttlmInf><SttlmMtd>INDA</SttlmMtd></SttlmInf></GrpHdr>
                <CdtTrfTxInf><PmtId><EndToEndId>E</EndToEndId></PmtId><IntrBkSttlmAmt Ccy="EUR">1.00</IntrBkSttlmAmt>
                <ChrgBr>SHAR</ChrgBr><Dbtr><Nm>Test Co</Nm><PstlAdr>%s</PstlAdr></Dbtr>
                <DbtrAgt><FinInstnId><BICFI>TESTGB2LXXX</BICFI></FinInstnId></DbtrAgt>
                <CdtrAgt><FinInstnId><BICFI>TESTIE2DXXX</BICFI></FinInstnId></CdtrAgt>
                <Cdtr><Nm>Other Co</Nm></Cdtr></CdtTrfTxInf>
                </FIToFICstmrCdtTrf></Document>""".formatted(pstlAdrBody);
    }

    @Test
    void recordsEveryErrorAndKeepsGoing() {
        // Three separate problems: Ctry lower case, BldgNb over 16, and an empty TwnNm. javax.xml.validation
        // reports each facet violation twice (the facet error, then "value is not valid for its type"), and
        // every one is recorded, so three problems give six errors.
        var file = TestSupport.file(withAddress(
                "<BldgNb>12345678901234567</BldgNb><TwnNm></TwnNm><Ctry>ie</Ctry>"));
        SchemaValidation v = validator.validate(file, pacs());
        assertThat(v.valid()).isFalse();
        assertThat(v.errorCount()).isEqualTo(6);
        assertThat(v.errors()).hasSize(6);
        assertThat(v.errors()).extracting(SchemaError::message)
                .anySatisfy(m -> assertThat(m).contains("BldgNb"))
                .anySatisfy(m -> assertThat(m).contains("TwnNm"))
                .anySatisfy(m -> assertThat(m).contains("ie"));
        assertThat(v.errors()).allSatisfy(e -> {
            assertThat(e.severity()).isEqualTo("ERROR");
            assertThat(e.line()).isPositive();
        });
    }

    @Test
    void usesTheXsdLengthLimitsNotTheSpecTableOnes() {
        // 100 characters is over the spec table's 70 for StrtNm but within the XSD's 140: no error.
        var file = TestSupport.file(withAddress("<StrtNm>" + "S".repeat(100) + "</StrtNm><TwnNm>Dublin</TwnNm><Ctry>IE</Ctry>"));
        assertThat(validator.validate(file, pacs()).valid()).isTrue();
        var tooLong = TestSupport.file(withAddress("<StrtNm>" + "S".repeat(141) + "</StrtNm>"));
        // One violation, reported as the facet error (names the limit) plus the type error (names the element).
        assertThat(validator.validate(tooLong, pacs()).errors()).extracting(SchemaError::message)
                .hasSize(2)
                .anySatisfy(m -> assertThat(m).contains("maxLength '140'"))
                .anySatisfy(m -> assertThat(m).contains("element 'StrtNm'"));
    }

    @Test
    void capsRecordedErrorsButStillCountsAllOfThem() {
        var capped = new SchemaValidator(TestSupport.properties(2, TestSupport.PACS008, TestSupport.PAIN001));
        var file = TestSupport.file(withAddress("<BldgNb>12345678901234567</BldgNb><TwnNm></TwnNm><Ctry>ie</Ctry>"));
        SchemaValidation v = capped.validate(file, pacs());
        assertThat(v.errors()).hasSize(2);
        assertThat(v.errorCount()).isEqualTo(6);
    }

    @Test
    void aMessageThatIsNotWellFormedIsRejectedNotRecorded() {
        var file = TestSupport.file("<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14\"><unclosed></Document>");
        assertThatThrownBy(() -> validator.validate(file, pacs()))
                .isInstanceOfSatisfying(IngestException.class, e -> assertThat(e.code()).isEqualTo("MALFORMED_XML"));
    }
}
