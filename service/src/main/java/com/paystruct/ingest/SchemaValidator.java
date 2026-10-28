package com.paystruct.ingest;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.xml.XMLConstants;
import javax.xml.transform.stream.StreamSource;
import javax.xml.validation.Validator;
import org.springframework.stereotype.Component;
import org.xml.sax.ErrorHandler;
import org.xml.sax.SAXException;
import org.xml.sax.SAXParseException;

/**
 * Validates a message against its XSD with javax.xml.validation. Errors are recorded and validation keeps
 * going: bad input is what PayStruct exists to fix. Only a fatal (not well-formed) error stops it.
 */
@Component
public class SchemaValidator {

    private final int maxRecordedErrors;

    public SchemaValidator(IngestProperties properties) {
        this.maxRecordedErrors = properties.maxSchemaErrors();
    }

    public SchemaValidation validate(Path file, MessageType type) {
        Validator validator = type.schema().newValidator();
        try {
            validator.setProperty(XMLConstants.ACCESS_EXTERNAL_DTD, "");
            validator.setProperty(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        } catch (SAXException e) {
            throw new IllegalStateException("Validator does not support the secure properties", e);
        }
        try {
            // Defence in depth: refuse a DOCTYPE here too, should this method ever be called on unchecked input.
            validator.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        } catch (SAXException ignored) {
            // Not every JAXP implementation exposes this feature; the detection pass already rejects DOCTYPE.
        }
        Collector collector = new Collector(maxRecordedErrors);
        validator.setErrorHandler(collector);
        // A DOCTYPE has already been rejected by the type-detection pass, so the validator never sees one.
        try (InputStream in = Files.newInputStream(file)) {
            validator.validate(new StreamSource(in));
        } catch (SAXParseException e) {
            throw SafeXml.malformed(e);
        } catch (SAXException | IOException e) {
            throw new IllegalStateException("Schema validation failed unexpectedly", e);
        }
        return new SchemaValidation(List.copyOf(collector.errors), collector.count);
    }

    private static final class Collector implements ErrorHandler {
        private final int cap;
        private final List<SchemaError> errors = new ArrayList<>();
        private int count;

        private Collector(int cap) {
            this.cap = cap;
        }

        @Override
        public void warning(SAXParseException e) {
            // Warnings are not schema errors.
        }

        @Override
        public void error(SAXParseException e) {
            record("ERROR", e);
        }

        @Override
        public void fatalError(SAXParseException e) throws SAXException {
            throw e;
        }

        private void record(String severity, SAXParseException e) {
            count++;
            if (errors.size() < cap) {
                errors.add(new SchemaError(severity, e.getLineNumber(), e.getColumnNumber(), e.getMessage()));
            }
        }
    }
}
