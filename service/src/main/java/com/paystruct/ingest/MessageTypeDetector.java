package com.paystruct.ingest;

import java.nio.file.Path;
import java.util.List;
import javax.xml.stream.XMLStreamConstants;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

/** Finds the message type from the namespace of the root element. Unknown types are rejected with HTTP 400. */
@Component
public class MessageTypeDetector {

    private final MessageTypeRegistry registry;

    public MessageTypeDetector(MessageTypeRegistry registry) {
        this.registry = registry;
    }

    public MessageType detect(Path file) {
        String namespace;
        try (SafeXml.Reader in = SafeXml.open(file)) {
            int event;
            do {
                if (!in.hasNext()) {
                    throw SafeXml.malformed(new IllegalStateException("no root element"));
                }
                event = in.next(); // a DOCTYPE before the root is rejected here
            } while (event != XMLStreamConstants.START_ELEMENT);
            namespace = in.stream().getNamespaceURI();
        }
        return registry.byNamespace(namespace).orElseThrow(() -> unsupported(namespace, registry.supportedNamespaces()));
    }

    private static IngestException unsupported(String namespace, List<String> supported) {
        String found = namespace == null || namespace.isEmpty() ? "no namespace" : "namespace " + namespace;
        return new IngestException(HttpStatus.BAD_REQUEST, "UNSUPPORTED_MESSAGE_TYPE",
                "Unsupported message type: the root element has " + found + ". Supported namespaces: "
                        + String.join(", ", supported));
    }
}
