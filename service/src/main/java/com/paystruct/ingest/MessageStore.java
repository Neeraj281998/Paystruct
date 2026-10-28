package com.paystruct.ingest;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** Persistence for ingested messages. The production implementation is Postgres; tests may use memory. */
public interface MessageStore {

    Optional<MessageReport> findByHash(String contentHash);

    Optional<MessageReport> findById(UUID messageId);

    /**
     * Stores the message, its address jobs and its schema report in one transaction.
     *
     * @return false, storing nothing, when a message with the same content hash already exists
     */
    boolean save(UUID messageId, String contentHash, String messageType, SchemaValidation validation, List<AddressJob> jobs);
}
