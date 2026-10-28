package com.paystruct.api;

import com.paystruct.ingest.IngestException;
import com.paystruct.ingest.IngestionService;
import com.paystruct.ingest.MessageReport;
import jakarta.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MessageController {

    private final IngestionService ingestion;

    public MessageController(IngestionService ingestion) {
        this.ingestion = ingestion;
    }

    /** Takes the raw XML body straight from the request stream so the size cap is enforced on bytes read. */
    @PostMapping(path = "/v1/messages", consumes = {MediaType.APPLICATION_XML_VALUE, MediaType.TEXT_XML_VALUE},
            produces = MediaType.APPLICATION_JSON_VALUE)
    public MessageReport post(HttpServletRequest request) throws IOException {
        return ingestion.ingest(request.getInputStream(), request.getContentLengthLong());
    }

    @GetMapping(path = "/v1/messages/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
    public MessageReport get(@PathVariable UUID id) {
        return ingestion.get(id)
                .orElseThrow(() -> new IngestException(HttpStatus.NOT_FOUND, "MESSAGE_NOT_FOUND", "No message with id " + id));
    }
}
