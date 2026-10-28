package com.paystruct.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class PostalAddressSchemaTest {

    private final MessageTypeRegistry registry = TestSupport.registry();

    private PostalAddressSchema address(String namespace) {
        return registry.byNamespace(namespace).orElseThrow().address();
    }

    @Test
    void readsTheTypeNameFromTheXsd() {
        assertThat(address(TestSupport.PACS008.namespace()).typeName()).isEqualTo("PostalAddress27");
        assertThat(address(TestSupport.PAIN001.namespace()).typeName()).isEqualTo("PostalAddress27");
    }

    @Test
    void keepsTheElementOrderOfTheXsdSequence() {
        List<String> names = address(TestSupport.PACS008.namespace()).elements().stream()
                .map(PostalAddressElement::name).toList();
        assertThat(names).containsExactly("AdrTp", "CareOf", "Dept", "SubDept", "StrtNm", "BldgNb", "BldgNm", "Flr",
                "UnitNb", "PstBx", "Room", "PstCd", "TwnNm", "TwnLctnNm", "DstrctNm", "CtrySubDvsn", "Ctry", "AdrLine");
    }

    @Test
    void readsMaximumLengthsFromTheXsdNotFromTheSpecTable() {
        PostalAddressSchema a = address(TestSupport.PACS008.namespace());
        // The spec table says 70, 35, 35; the supplied XSD says 140.
        assertThat(a.element("StrtNm").orElseThrow().maxLength()).isEqualTo(140);
        assertThat(a.element("BldgNm").orElseThrow().maxLength()).isEqualTo(140);
        assertThat(a.element("TwnNm").orElseThrow().maxLength()).isEqualTo(140);
        assertThat(a.element("TwnLctnNm").orElseThrow().maxLength()).isEqualTo(140);
        assertThat(a.element("DstrctNm").orElseThrow().maxLength()).isEqualTo(140);
        // Unchanged from the spec table.
        assertThat(a.element("BldgNb").orElseThrow().maxLength()).isEqualTo(16);
        assertThat(a.element("PstCd").orElseThrow().maxLength()).isEqualTo(16);
        assertThat(a.element("PstBx").orElseThrow().maxLength()).isEqualTo(16);
        assertThat(a.element("CtrySubDvsn").orElseThrow().maxLength()).isEqualTo(35);
        assertThat(a.element("Dept").orElseThrow().maxLength()).isEqualTo(70);
        assertThat(a.element("Flr").orElseThrow().maxLength()).isEqualTo(70);
        assertThat(a.element("Room").orElseThrow().maxLength()).isEqualTo(70);
        // Elements the spec table does not list.
        assertThat(a.element("CareOf").orElseThrow().maxLength()).isEqualTo(140);
        assertThat(a.element("UnitNb").orElseThrow().maxLength()).isEqualTo(16);
    }

    @Test
    void readsCountryCodeAsAPatternAndAdrLineAsUpToSevenLines() {
        PostalAddressSchema a = address(TestSupport.PACS008.namespace());
        PostalAddressElement ctry = a.element("Ctry").orElseThrow();
        assertThat(ctry.maxLength()).isNull();
        assertThat(ctry.pattern()).isEqualTo("[A-Z]{2,2}");
        PostalAddressElement line = a.element("AdrLine").orElseThrow();
        assertThat(line.maxLength()).isEqualTo(70);
        assertThat(line.maxOccurs()).isEqualTo(7);
    }

    @Test
    void noElementIsRequiredByTheXsd() {
        assertThat(address(TestSupport.PACS008.namespace()).elements()).allSatisfy(e -> assertThat(e.minOccurs()).isZero());
    }

    @Test
    void discreteFieldsExcludeAdrLineAndAdrTp() {
        PostalAddressSchema a = address(TestSupport.PACS008.namespace());
        assertThat(a.isDiscreteField("TwnNm")).isTrue();
        assertThat(a.isDiscreteField("AdrLine")).isFalse();
        assertThat(a.isDiscreteField("AdrTp")).isFalse();
        assertThat(a.isDiscreteField("Nope")).isFalse();
    }

    @Test
    void bothSuppliedVersionsDefineTheSameAddressElements() {
        assertThat(address(TestSupport.PAIN001.namespace()).elements())
                .isEqualTo(address(TestSupport.PACS008.namespace()).elements());
    }
}
