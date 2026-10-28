package com.paystruct.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AddressJobExtractorTest {

    private static final String PACS_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14";

    private final MessageTypeRegistry registry = TestSupport.registry();
    private final AddressJobExtractor extractor = new AddressJobExtractor();
    private final UUID messageId = UUID.randomUUID();

    private List<AddressJob> extract(String sample, String namespace) {
        return extractor.extract(TestSupport.sampleFile(sample), registry.byNamespace(namespace).orElseThrow(), messageId);
    }

    /** A pacs.008 whose CdtTrfTxInf holds the given extra elements after ChrgBr. */
    private List<AddressJob> extractXml(String txBody) {
        String xml = "<Document xmlns=\"" + PACS_NS + "\"><FIToFICstmrCdtTrf><CdtTrfTxInf>" + txBody
                + "</CdtTrfTxInf></FIToFICstmrCdtTrf></Document>";
        return extractor.extract(TestSupport.file(xml), registry.byNamespace(PACS_NS).orElseThrow(), messageId);
    }

    @Test
    void unstructuredPacs008GivesOneJobPerPartyAndAgentWithAnAddress() {
        List<AddressJob> jobs = extract("pacs008-unstructured.xml", PACS_NS);
        assertThat(jobs).extracting(AddressJob::role)
                .containsExactly(PartyRole.DEBTOR, PartyRole.CREDITOR_AGENT, PartyRole.CREDITOR);
        // DbtrAgt has a BIC and no address: no job.
        assertThat(jobs).extracting(AddressJob::messageType).containsOnly("pacs.008");
        assertThat(jobs).extracting(AddressJob::messageId).containsOnly(messageId);
        assertThat(jobs).extracting(AddressJob::jobId).doesNotHaveDuplicates();
    }

    @Test
    void keepsRawLinesExactlyAsReceived() {
        AddressJob creditor = extract("pacs008-unstructured.xml", PACS_NS).get(2);
        assertThat(creditor.rawLines()).containsExactly("Unit 4 Block B Docklands Business Park", "Dublin 1 D01 K2X7 Ireland");
        assertThat(creditor.existing().fields()).isEmpty();
        assertThat(creditor.alreadyStructured()).isFalse();
    }

    @Test
    void recordsWhereTheAddressSitsInTheMessage() {
        AddressJob debtor = extract("pacs008-unstructured.xml", PACS_NS).get(0);
        assertThat(debtor.xmlPath()).isEqualTo("/Document/FIToFICstmrCdtTrf[1]/CdtTrfTxInf[1]/Dbtr[1]/PstlAdr[1]");
        AddressJob agent = extract("pacs008-unstructured.xml", PACS_NS).get(1);
        assertThat(agent.xmlPath()).isEqualTo("/Document/FIToFICstmrCdtTrf[1]/CdtTrfTxInf[1]/CdtrAgt[1]/FinInstnId[1]/PstlAdr[1]");
    }

    @Test
    void countryHintComesFromTheBankBicWhenThePartyHasNone() {
        List<AddressJob> jobs = extract("pacs008-unstructured.xml", PACS_NS);
        assertThat(jobs.get(0).countryHint()).isEqualTo("GB"); // Dbtr: DbtrAgt BICFI TESTGB2LXXX
        assertThat(jobs.get(2).countryHint()).isNull();        // Cdtr: CdtrAgt has no BIC
        assertThat(jobs.get(1).countryHint()).isNull();        // CdtrAgt itself has no BIC
    }

    @Test
    void anAgentWithABicGetsItsOwnCountryHint() {
        List<AddressJob> jobs = extractXml("<CdtrAgt><FinInstnId><BICFI>TESTFR2PXXX</BICFI><Nm>Banque</Nm>"
                + "<PstlAdr><AdrLine>3 Rue X</AdrLine></PstlAdr></FinInstnId></CdtrAgt>");
        assertThat(jobs).hasSize(1);
        assertThat(jobs.get(0).role()).isEqualTo(PartyRole.CREDITOR_AGENT);
        assertThat(jobs.get(0).countryHint()).isEqualTo("FR");
    }

    @Test
    void aPartysOwnBicBeatsItsBanksBic() {
        List<AddressJob> jobs = extractXml("<Dbtr><PstlAdr><AdrLine>x</AdrLine></PstlAdr>"
                + "<Id><OrgId><AnyBIC>TESTIE2DXXX</AnyBIC></OrgId></Id></Dbtr>"
                + "<DbtrAgt><FinInstnId><BICFI>TESTGB2LXXX</BICFI></FinInstnId></DbtrAgt>");
        assertThat(jobs.get(0).countryHint()).isEqualTo("IE");
    }

    @Test
    void aMalformedBicGivesNoHint() {
        List<AddressJob> jobs = extractXml("<Dbtr><PstlAdr><AdrLine>x</AdrLine></PstlAdr></Dbtr>"
                + "<DbtrAgt><FinInstnId><BICFI>nope</BICFI></FinInstnId></DbtrAgt>");
        assertThat(jobs.get(0).countryHint()).isNull();
    }

    @Test
    void ultimatePartiesUseTheirMainPartysBank() {
        List<AddressJob> jobs = extractXml("<UltmtDbtr><PstlAdr><AdrLine>x</AdrLine></PstlAdr></UltmtDbtr>"
                + "<DbtrAgt><FinInstnId><BICFI>TESTDEHHXXX</BICFI></FinInstnId></DbtrAgt>");
        assertThat(jobs.get(0).role()).isEqualTo(PartyRole.ULTIMATE_DEBTOR);
        assertThat(jobs.get(0).countryHint()).isEqualTo("DE");
    }

    @Test
    void structuredPacs008CoversFourRolesAndMarksEveryAddressAlreadyStructured() {
        List<AddressJob> jobs = extract("pacs008-structured.xml", PACS_NS);
        assertThat(jobs).extracting(AddressJob::role).containsExactly(
                PartyRole.ULTIMATE_DEBTOR, PartyRole.DEBTOR, PartyRole.CREDITOR_AGENT, PartyRole.CREDITOR, PartyRole.ULTIMATE_CREDITOR);
        assertThat(jobs).allSatisfy(j -> {
            assertThat(j.alreadyStructured()).isTrue();
            assertThat(j.rawLines()).isEmpty();
        });
        assertThat(jobs.get(0).countryHint()).isEqualTo("DE");
        assertThat(jobs.get(4).countryHint()).isNull();
    }

    @Test
    void existingFieldsAreKeyedByXsdNameInXsdOrderWithTheAddressType() {
        AddressJob debtor = extract("pacs008-structured.xml", PACS_NS).get(1);
        assertThat(debtor.existing().fields()).containsExactly(
                java.util.Map.entry("AdrTp", "BIZZ"),
                java.util.Map.entry("StrtNm", "Lindenallee"),
                java.util.Map.entry("BldgNb", "27"),
                java.util.Map.entry("PstCd", "20095"),
                java.util.Map.entry("TwnNm", "Hamburg"),
                java.util.Map.entry("Ctry", "DE"));
    }

    @Test
    void aHybridAddressIsNotAlreadyStructured() {
        List<AddressJob> jobs = extractXml("<Cdtr><PstlAdr><TwnNm>Cork</TwnNm><Ctry>IE</Ctry>"
                + "<AdrLine>7 Orchard Lane</AdrLine></PstlAdr></Cdtr>");
        assertThat(jobs.get(0).alreadyStructured()).isFalse();
        assertThat(jobs.get(0).existing().fields()).containsEntry("TwnNm", "Cork").containsEntry("Ctry", "IE");
        assertThat(jobs.get(0).rawLines()).containsExactly("7 Orchard Lane");
    }

    @Test
    void structuredWithoutTownOrCountryIsNotAlreadyStructured() {
        assertThat(extractXml("<Cdtr><PstlAdr><StrtNm>Main St</StrtNm><Ctry>IE</Ctry></PstlAdr></Cdtr>").get(0)
                .alreadyStructured()).isFalse();
        assertThat(extractXml("<Cdtr><PstlAdr><StrtNm>Main St</StrtNm><TwnNm>Cork</TwnNm></PstlAdr></Cdtr>").get(0)
                .alreadyStructured()).isFalse();
    }

    @Test
    void aProprietaryAddressTypeIsKeptAsItsId() {
        AddressJob job = extractXml("<Cdtr><PstlAdr><AdrTp><Prtry><Id>SYNTH-TYPE</Id></Prtry></AdrTp>"
                + "<TwnNm>Cork</TwnNm><Ctry>IE</Ctry></PstlAdr></Cdtr>").get(0);
        assertThat(job.existing().fields()).containsEntry("AdrTp", "SYNTH-TYPE");
        assertThat(job.alreadyStructured()).isTrue();
    }

    @Test
    void aPartyWithoutAPostalAddressGivesNoJob() {
        assertThat(extractXml("<Cdtr><Nm>No address</Nm></Cdtr>")).isEmpty();
    }

    @Test
    void remittanceAndChequeAddressesAreOutOfScope() {
        assertThat(extractXml("<RmtInf><Strd><RfrdDocInf/></Strd></RmtInf>"
                + "<RmtLctnDtls><PstlAdr><Nm>Someone</Nm><Adr><TwnNm>Cork</TwnNm></Adr></PstlAdr></RmtLctnDtls>")).isEmpty();
    }

    @Test
    void pain001GivesJobsForEveryTransactionWithTransactionIndicesInThePath() {
        List<AddressJob> jobs = extract("pain001-unstructured.xml", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.13");
        assertThat(jobs).extracting(AddressJob::role).containsExactly(PartyRole.DEBTOR, PartyRole.CREDITOR, PartyRole.CREDITOR);
        assertThat(jobs).extracting(AddressJob::messageType).containsOnly("pain.001");
        assertThat(jobs.get(1).xmlPath()).isEqualTo("/Document/CstmrCdtTrfInitn[1]/PmtInf[1]/CdtTrfTxInf[1]/Cdtr[1]/PstlAdr[1]");
        assertThat(jobs.get(2).xmlPath()).isEqualTo("/Document/CstmrCdtTrfInitn[1]/PmtInf[1]/CdtTrfTxInf[2]/Cdtr[1]/PstlAdr[1]");
    }

    @Test
    void pain001HintsComeFromThePartyBicOrTheTransactionsOwnBank() {
        List<AddressJob> jobs = extract("pain001-unstructured.xml", "urn:iso:std:iso:20022:tech:xsd:pain.001.001.13");
        assertThat(jobs.get(0).countryHint()).isEqualTo("IE"); // Dbtr AnyBIC TESTIE2DXXX
        assertThat(jobs.get(1).countryHint()).isEqualTo("NL"); // CdtrAgt of transaction 1
        assertThat(jobs.get(2).countryHint()).isNull();        // transaction 2 has no CdtrAgt
    }
}
