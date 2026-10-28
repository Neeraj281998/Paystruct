package com.paystruct.ingest;

import javax.xml.validation.Schema;

/** A supported message version: namespace, short type name ("pacs.008"), compiled schema and address definition. */
public record MessageType(String namespace, String type, String xsd, Schema schema, PostalAddressSchema address) {}
