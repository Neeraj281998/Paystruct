package com.paystruct.ingest;

import java.util.List;

/** What ingestion learned about one message, before anything is stored. */
public record Analysis(MessageType type, SchemaValidation validation, List<AddressJob> jobs) {}
