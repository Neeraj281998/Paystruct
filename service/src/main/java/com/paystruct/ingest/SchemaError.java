package com.paystruct.ingest;

/** One XSD validation problem. Line and column are -1 when the parser gave none. */
public record SchemaError(String severity, int line, int column, String message) {}
