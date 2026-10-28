package com.paystruct.ingest;

import org.springframework.http.HttpStatus;

/** A request PayStruct refuses before processing; carries the HTTP status and a stable error code. */
public class IngestException extends RuntimeException {
    private final HttpStatus status;
    private final String code;

    public IngestException(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public IngestException(HttpStatus status, String code, String message, Throwable cause) {
        super(message, cause);
        this.status = status;
        this.code = code;
    }

    public HttpStatus status() {
        return status;
    }

    public String code() {
        return code;
    }
}
