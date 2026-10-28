package com.paystruct.api;

import com.paystruct.ingest.AddressJob;
import com.paystruct.ingest.MessageReport;
import com.paystruct.ingest.MessageStore;
import com.paystruct.ingest.SchemaValidation;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/** A MessageStore for tests that need the HTTP layer but not a database. */
class InMemoryMessageStore implements MessageStore {

    final Map<String, MessageReport> byHash = new ConcurrentHashMap<>();

    @Override
    public Optional<MessageReport> findByHash(String contentHash) {
        return Optional.ofNullable(byHash.get(contentHash));
    }

    @Override
    public Optional<MessageReport> findById(UUID messageId) {
        return byHash.values().stream().filter(r -> r.messageId().equals(messageId)).findFirst();
    }

    @Override
    public boolean save(UUID messageId, String contentHash, String messageType, SchemaValidation validation, List<AddressJob> jobs) {
        MessageReport report = new MessageReport(messageId, messageType, "RECEIVED", validation.valid(),
                validation.errorCount(), validation.errors(), false, jobs);
        return byHash.putIfAbsent(contentHash, report) == null;
    }
}
