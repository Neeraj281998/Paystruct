package com.paystruct.ingest;

/**
 * One child of the postal address type, read from the XSD.
 *
 * @param maxOccurs   -1 means unbounded
 * @param maxLength   null when the XSD gives none (complex types, pattern-restricted codes)
 * @param pattern     the XSD pattern facet, if any (for example {@code [A-Z]{2,2}} for Ctry)
 * @param complex     true for elements with child elements (AdrTp)
 */
public record PostalAddressElement(
        String name, int order, int minOccurs, int maxOccurs, Integer maxLength, String pattern, boolean complex) {}
