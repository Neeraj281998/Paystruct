package com.paystruct.ingest;

import java.util.List;
import java.util.UUID;

/**
 * The response to POST /v1/messages and GET /v1/messages/{id}.
 *
 * @param schemaErrors     recorded errors, capped; schemaErrorCount is the true total
 * @param duplicate        true when this exact content (same SHA-256) was received before
 */
public record MessageReport(
        UUID messageId,
        String messageType,
        String status,
        boolean inputValid,
        int schemaErrorCount,
        List<SchemaError> schemaErrors,
        boolean duplicate,
        List<AddressJob> addressJobs) {

    public MessageReport withDuplicate(boolean value) {
        return new MessageReport(messageId, messageType, status, inputValid, schemaErrorCount, schemaErrors, value, addressJobs);
    }
}
