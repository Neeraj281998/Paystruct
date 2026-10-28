package com.paystruct.ingest;

import java.util.List;

/**
 * @param errors     the recorded errors, capped at paystruct.ingest.max-schema-errors
 * @param errorCount every error found, including those past the cap
 */
public record SchemaValidation(List<SchemaError> errors, int errorCount) {
    public boolean valid() {
        return errorCount == 0;
    }
}
