package com.paystruct.ingest;

import java.util.List;
import java.util.UUID;

/**
 * One address to structure: one party (or agent) with a PstlAdr block. This is the record from the spec plus
 * two additions: jobId (every later write is keyed by it) and alreadyStructured (later phases skip those).
 *
 * @param xmlPath           where the address sits, for example /Document/FIToFICstmrCdtTrf[1]/CdtTrfTxInf[1]/Cdtr[1]/PstlAdr[1]
 * @param rawLines          the AdrLine values as received
 * @param existing          any fields already structured
 * @param countryHint       characters 5 and 6 of a BIC (the party's own, else its bank's), or null
 * @param alreadyStructured no AdrLine, and both TwnNm and Ctry present
 */
public record AddressJob(
        UUID jobId,
        UUID messageId,
        String messageType,
        PartyRole role,
        String xmlPath,
        List<String> rawLines,
        StructuredAddress existing,
        String countryHint,
        boolean alreadyStructured) {}
