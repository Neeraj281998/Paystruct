package com.paystruct.ingest;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/**
 * Receive, deduplicate, analyse, store. The body is spooled to a temporary file while its SHA-256 is computed,
 * so the cap is enforced on the bytes actually read and the parsers stream from disk instead of holding the
 * message in memory. Rejected requests (too big, DOCTYPE, not XML, unknown type) store nothing.
 */
@Service
public class IngestionService {

    private static final int BUFFER = 64 * 1024;

    private final MessageAnalyzer analyzer;
    private final MessageStore store;
    private final long maxBytes;

    public IngestionService(MessageAnalyzer analyzer, MessageStore store, IngestProperties properties) {
        this.analyzer = analyzer;
        this.store = store;
        this.maxBytes = properties.maxRequestSize().toBytes();
    }

    /** @param declaredLength the Content-Length header, or -1 when absent (chunked) */
    public MessageReport ingest(InputStream body, long declaredLength) {
        if (declaredLength > maxBytes) {
            throw tooLarge();
        }
        Path spool = null;
        try {
            spool = Files.createTempFile("paystruct-ingest-", ".xml");
            String hash = spoolAndHash(body, spool);

            Optional<MessageReport> existing = store.findByHash(hash);
            if (existing.isPresent()) {
                return existing.get().withDuplicate(true);
            }

            UUID messageId = UUID.randomUUID();
            Analysis analysis = analyzer.analyze(spool, messageId);
            boolean saved = store.save(messageId, hash, analysis.type().type(), analysis.validation(), analysis.jobs());
            if (!saved) { // the same content arrived concurrently and won the insert
                return store.findByHash(hash).orElseThrow().withDuplicate(true);
            }
            return new MessageReport(
                    messageId,
                    analysis.type().type(),
                    JdbcMessageStore.STATUS_RECEIVED,
                    analysis.validation().valid(),
                    analysis.validation().errorCount(),
                    analysis.validation().errors(),
                    false,
                    analysis.jobs());
        } catch (IOException e) {
            throw new IllegalStateException("Could not spool the request body", e);
        } finally {
            if (spool != null) {
                try {
                    Files.deleteIfExists(spool);
                } catch (IOException ignored) {
                    // a leftover temp file is harmless and cleaned by the OS
                }
            }
        }
    }

    public Optional<MessageReport> get(UUID messageId) {
        return store.findById(messageId);
    }

    private String spoolAndHash(InputStream body, Path spool) throws IOException {
        MessageDigest sha256;
        try {
            sha256 = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
        long total = 0;
        byte[] buffer = new byte[BUFFER];
        try (var out = Files.newOutputStream(spool)) {
            int n;
            while ((n = body.read(buffer)) != -1) {
                total += n;
                if (total > maxBytes) {
                    throw tooLarge();
                }
                sha256.update(buffer, 0, n);
                out.write(buffer, 0, n);
            }
        }
        if (total == 0) {
            throw new IngestException(HttpStatus.BAD_REQUEST, "EMPTY_BODY", "The request body is empty.");
        }
        return HexFormat.of().formatHex(sha256.digest());
    }

    private IngestException tooLarge() {
        return new IngestException(HttpStatus.PAYLOAD_TOO_LARGE, "PAYLOAD_TOO_LARGE",
                "The request body exceeds the limit of " + maxBytes + " bytes.");
    }
}
