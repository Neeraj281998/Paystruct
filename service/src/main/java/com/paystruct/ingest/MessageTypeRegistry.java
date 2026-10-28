package com.paystruct.ingest;

import java.io.IOException;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import javax.xml.XMLConstants;
import javax.xml.transform.stream.StreamSource;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.xml.sax.SAXException;

/** The supported message versions, built from configuration at startup. Schemas are compiled once. */
@Component
public class MessageTypeRegistry {

    private final Map<String, MessageType> byNamespace = new LinkedHashMap<>();

    public MessageTypeRegistry(IngestProperties properties) {
        for (IngestProperties.MessageTypeConfig c : properties.messageTypes()) {
            byNamespace.put(c.namespace(), load(c));
        }
    }

    public Optional<MessageType> byNamespace(String namespace) {
        return Optional.ofNullable(namespace == null ? null : byNamespace.get(namespace));
    }

    public List<String> supportedNamespaces() {
        return List.copyOf(byNamespace.keySet());
    }

    private static MessageType load(IngestProperties.MessageTypeConfig c) {
        try {
            SchemaFactory sf = SchemaFactory.newInstance(XMLConstants.W3C_XML_SCHEMA_NS_URI);
            sf.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            sf.setProperty(XMLConstants.ACCESS_EXTERNAL_DTD, "");
            sf.setProperty(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
            ClassPathResource xsd = new ClassPathResource(c.xsd());
            Schema schema;
            try (InputStream in = xsd.getInputStream()) {
                schema = sf.newSchema(new StreamSource(in));
            }
            PostalAddressSchema address;
            try (InputStream in = xsd.getInputStream()) {
                address = PostalAddressSchema.load(in);
            }
            return new MessageType(c.namespace(), c.type(), c.xsd(), schema, address);
        } catch (SAXException | IOException e) {
            throw new IllegalStateException("Cannot load schema " + c.xsd(), e);
        }
    }
}
