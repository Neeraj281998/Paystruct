package com.paystruct.ingest;

import java.nio.file.Path;
import java.util.UUID;
import org.springframework.stereotype.Component;

/** Detect the type, validate against the XSD, extract address jobs. No storage: usable without a database. */
@Component
public class MessageAnalyzer {

    private final MessageTypeDetector detector;
    private final SchemaValidator validator;
    private final AddressJobExtractor extractor;

    public MessageAnalyzer(MessageTypeDetector detector, SchemaValidator validator, AddressJobExtractor extractor) {
        this.detector = detector;
        this.validator = validator;
        this.extractor = extractor;
    }

    public Analysis analyze(Path file, UUID messageId) {
        MessageType type = detector.detect(file);
        SchemaValidation validation = validator.validate(file, type);
        return new Analysis(type, validation, extractor.extract(file, type, messageId));
    }
}
