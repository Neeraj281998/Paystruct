package com.paystruct.ingest;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.XMLConstants;
import javax.xml.stream.XMLInputFactory;
import javax.xml.stream.XMLStreamConstants;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamReader;
import org.springframework.http.HttpStatus;

/**
 * The only place an XMLStreamReader is created. DTDs and external entities are switched off, and any
 * DOCTYPE is rejected outright, so XXE and entity-expansion payloads never reach a parser that could
 * act on them. Reads from a file, element by element (StAX), so a large message is never held whole in memory.
 */
public final class SafeXml {

    private SafeXml() {}

    public static XMLInputFactory inputFactory() {
        XMLInputFactory f = XMLInputFactory.newFactory();
        f.setProperty(XMLInputFactory.SUPPORT_DTD, false);
        f.setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES, false);
        f.setProperty(XMLInputFactory.IS_COALESCING, true);
        setIfSupported(f, XMLConstants.ACCESS_EXTERNAL_DTD, "");
        setIfSupported(f, XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        return f;
    }

    private static void setIfSupported(XMLInputFactory f, String property, Object value) {
        if (f.isPropertySupported(property)) {
            f.setProperty(property, value);
        }
    }

    /** A StAX reader over a file. Closing it closes the file too. */
    public static Reader open(Path file) {
        try {
            InputStream in = Files.newInputStream(file);
            try {
                return new Reader(in, inputFactory().createXMLStreamReader(in));
            } catch (XMLStreamException | RuntimeException e) {
                in.close();
                throw malformed(e);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Cannot read " + file, e);
        }
    }

    public static IngestException malformed(Exception cause) {
        return new IngestException(HttpStatus.BAD_REQUEST, "MALFORMED_XML",
                "The request body is not well-formed XML: " + firstLine(cause.getMessage()), cause);
    }

    public static IngestException dtdNotAllowed() {
        return new IngestException(HttpStatus.BAD_REQUEST, "DTD_NOT_ALLOWED",
                "DOCTYPE declarations are not allowed: DTDs and external entities are disabled.");
    }

    private static String firstLine(String s) {
        if (s == null) {
            return "parse error";
        }
        int nl = s.indexOf('\n');
        return nl < 0 ? s : s.substring(0, nl);
    }

    public static final class Reader implements AutoCloseable {
        private final InputStream in;
        private final XMLStreamReader reader;

        private Reader(InputStream in, XMLStreamReader reader) {
            this.in = in;
            this.reader = reader;
        }

        public XMLStreamReader stream() {
            return reader;
        }

        public boolean hasNext() {
            try {
                return reader.hasNext();
            } catch (XMLStreamException e) {
                throw malformed(e);
            }
        }

        /** Next event; a DOCTYPE or a parse error becomes an {@link IngestException}. */
        public int next() {
            try {
                int event = reader.next();
                if (event == XMLStreamConstants.DTD) {
                    throw dtdNotAllowed();
                }
                return event;
            } catch (XMLStreamException e) {
                throw malformed(e);
            }
        }

        @Override
        public void close() {
            try {
                reader.close();
            } catch (XMLStreamException ignored) {
                // nothing useful to do
            }
            try {
                in.close();
            } catch (IOException ignored) {
                // nothing useful to do
            }
        }
    }
}
