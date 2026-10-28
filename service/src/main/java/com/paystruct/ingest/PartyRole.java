package com.paystruct.ingest;

/** The role a party or agent plays in the message; decided by the element that holds the PstlAdr. */
public enum PartyRole {
    DEBTOR,
    CREDITOR,
    ULTIMATE_DEBTOR,
    ULTIMATE_CREDITOR,
    INITIATING_PARTY,
    DEBTOR_AGENT,
    CREDITOR_AGENT,
    INTERMEDIARY_AGENT,
    INSTRUCTING_AGENT,
    INSTRUCTED_AGENT,
    PREVIOUS_INSTRUCTING_AGENT,
    FORWARDING_AGENT,
    /** Any other party with a PstlAdr, for example an invoicer or garnishee. */
    OTHER
}
