package com.paystruct.ingest;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.unit.DataSize;

@ConfigurationProperties(prefix = "paystruct.ingest")
public record IngestProperties(DataSize maxRequestSize, int maxSchemaErrors, List<MessageTypeConfig> messageTypes) {

    /** One supported message version: its XML namespace, short type name and XSD on the classpath. */
    public record MessageTypeConfig(String namespace, String type, String xsd) {}
}
