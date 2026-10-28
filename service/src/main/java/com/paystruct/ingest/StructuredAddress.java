package com.paystruct.ingest;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The discrete address fields already present in a message, keyed by XSD element name ("TwnNm", "Ctry", ...),
 * in XSD sequence order. AdrLine is not included; it is carried separately as rawLines. AdrTp, when present, is
 * stored as its code or proprietary id.
 */
public record StructuredAddress(@JsonValue Map<String, String> fields) {

    @JsonCreator
    public StructuredAddress(Map<String, String> fields) {
        this.fields = Collections.unmodifiableMap(new LinkedHashMap<>(fields));
    }

    public static StructuredAddress empty() {
        return new StructuredAddress(Map.of());
    }

    public boolean has(String element) {
        String v = fields.get(element);
        return v != null && !v.isBlank();
    }
}
