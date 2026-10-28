package com.paystruct.ingest;

import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import javax.xml.stream.XMLStreamConstants;
import javax.xml.stream.XMLStreamReader;
import org.springframework.stereotype.Component;

/**
 * Streams a message once with StAX and creates one {@link AddressJob} per PstlAdr block of a party or agent.
 *
 * <p>Roles come from the element holding the PstlAdr (Dbtr, Cdtr, DbtrAgt, ...). Country hints come from the
 * BIC: the party's own AnyBIC, or else the BICFI of its bank (DbtrAgt for debtors, CdtrAgt for creditors),
 * found by walking up from the party to the nearest enclosing element that has one. Hints are resolved after
 * the pass, because in pacs.008 and pain.001 the bank can come after the party in document order.
 */
@Component
public class AddressJobExtractor {

    private static final Pattern BIC = Pattern.compile("[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?");

    /** Wrappers between a role element and its PstlAdr (agents: DbtrAgt/FinInstnId/PstlAdr). */
    private static final List<String> WRAPPERS = List.of("FinInstnId", "BrnchId");

    /** PstlAdr elements under these are remittance or cheque addresses (NameAndAddress), not parties. */
    private static final List<String> OUT_OF_SCOPE = List.of("RmtLctnDtls", "ChqFr", "DlvrTo");

    private static final Map<String, PartyRole> ROLES = Map.ofEntries(
            Map.entry("Dbtr", PartyRole.DEBTOR),
            Map.entry("Cdtr", PartyRole.CREDITOR),
            Map.entry("UltmtDbtr", PartyRole.ULTIMATE_DEBTOR),
            Map.entry("UltmtCdtr", PartyRole.ULTIMATE_CREDITOR),
            Map.entry("InitgPty", PartyRole.INITIATING_PARTY),
            Map.entry("DbtrAgt", PartyRole.DEBTOR_AGENT),
            Map.entry("CdtrAgt", PartyRole.CREDITOR_AGENT),
            Map.entry("IntrmyAgt1", PartyRole.INTERMEDIARY_AGENT),
            Map.entry("IntrmyAgt2", PartyRole.INTERMEDIARY_AGENT),
            Map.entry("IntrmyAgt3", PartyRole.INTERMEDIARY_AGENT),
            Map.entry("InstgAgt", PartyRole.INSTRUCTING_AGENT),
            Map.entry("InstdAgt", PartyRole.INSTRUCTED_AGENT),
            Map.entry("PrvsInstgAgt1", PartyRole.PREVIOUS_INSTRUCTING_AGENT),
            Map.entry("PrvsInstgAgt2", PartyRole.PREVIOUS_INSTRUCTING_AGENT),
            Map.entry("PrvsInstgAgt3", PartyRole.PREVIOUS_INSTRUCTING_AGENT),
            Map.entry("FwdgAgt", PartyRole.FORWARDING_AGENT));

    /** A parsed PstlAdr before its country hint is known. */
    private record Candidate(PartyRole role, String rolePath, String xmlPath, List<String> lines, StructuredAddress existing) {}

    private static final class Frame {
        final String name;
        final String path;
        final Map<String, Integer> childCounts = new HashMap<>();
        final StringBuilder text = new StringBuilder();

        Frame(String name, String path) {
            this.name = name;
            this.path = path;
        }
    }

    public List<AddressJob> extract(Path file, MessageType type, UUID messageId) {
        List<Candidate> candidates = new ArrayList<>();
        Map<String, String> bics = new HashMap<>(); // element path -> BIC text
        Deque<Frame> stack = new ArrayDeque<>();

        try (SafeXml.Reader in = SafeXml.open(file)) {
            XMLStreamReader r = in.stream();
            while (in.hasNext()) {
                int event = in.next();
                if (event == XMLStreamConstants.START_ELEMENT) {
                    String name = r.getLocalName();
                    Frame frame = push(stack, name);
                    if ("PstlAdr".equals(name)) {
                        Candidate c = readAddress(in, type.address(), stack, frame);
                        if (c != null) {
                            candidates.add(c);
                        }
                        stack.pop(); // readAddress consumed the element through its END_ELEMENT
                    }
                } else if (event == XMLStreamConstants.CHARACTERS) {
                    if (!stack.isEmpty()) {
                        stack.peek().text.append(r.getText());
                    }
                } else if (event == XMLStreamConstants.END_ELEMENT) {
                    Frame done = stack.pop();
                    if (("BICFI".equals(done.name) || "AnyBIC".equals(done.name)) && !done.text.isEmpty()) {
                        bics.put(done.path, done.text.toString().trim());
                    }
                }
            }
        }

        List<AddressJob> jobs = new ArrayList<>();
        for (Candidate c : candidates) {
            boolean structured = c.lines().isEmpty() && c.existing().has("TwnNm") && c.existing().has("Ctry");
            jobs.add(new AddressJob(UUID.randomUUID(), messageId, type.type(), c.role(), c.xmlPath(), c.lines(),
                    c.existing(), countryHint(c, bics), structured));
        }
        return jobs;
    }

    private static Frame push(Deque<Frame> stack, String name) {
        Frame parent = stack.peek();
        String path;
        if (parent == null) {
            path = "/" + name;
        } else {
            int index = parent.childCounts.merge(name, 1, Integer::sum);
            path = parent.path + "/" + name + "[" + index + "]";
        }
        Frame frame = new Frame(name, path);
        stack.push(frame);
        return frame;
    }

    /**
     * Reads the PstlAdr subtree the reader is positioned on, leaving it on that element's END_ELEMENT.
     * Returns null when this PstlAdr is out of scope (remittance or cheque address, or unknown holder).
     */
    private Candidate readAddress(SafeXml.Reader in, PostalAddressSchema schema, Deque<Frame> stack, Frame self) {
        // stack is innermost-first; self is stack.peek()
        List<Frame> ancestors = new ArrayList<>(stack);
        ancestors.remove(0);
        for (Frame a : ancestors) {
            if (OUT_OF_SCOPE.contains(a.name)) {
                skipRest(in);
                return null;
            }
        }
        PartyRole role = PartyRole.OTHER;
        String rolePath = ancestors.isEmpty() ? self.path : ancestors.get(0).path;
        for (Frame a : ancestors) {
            if (WRAPPERS.contains(a.name)) {
                continue;
            }
            role = ROLES.getOrDefault(a.name, PartyRole.OTHER);
            rolePath = a.path;
            break;
        }

        Map<String, String> found = new LinkedHashMap<>();
        List<String> lines = new ArrayList<>();
        String adrTp = null;
        XMLStreamReader r = in.stream();
        int depth = 1; // inside PstlAdr
        String current = null; // the direct child being read
        boolean inAdrTp = false;
        StringBuilder text = new StringBuilder();
        while (depth > 0) {
            switch (in.next()) {
                case XMLStreamConstants.START_ELEMENT -> {
                    depth++;
                    text.setLength(0);
                    if (depth == 2) {
                        current = r.getLocalName();
                        inAdrTp = PostalAddressSchema.ADDRESS_TYPE.equals(current);
                    }
                }
                case XMLStreamConstants.CHARACTERS -> text.append(r.getText());
                case XMLStreamConstants.END_ELEMENT -> {
                    String value = text.toString();
                    if (depth == 2) {
                        if (PostalAddressSchema.ADDRESS_LINE.equals(current)) {
                            lines.add(value);
                        } else if (schema.isDiscreteField(current)) {
                            found.putIfAbsent(current, value);
                        }
                        current = null;
                        inAdrTp = false;
                    } else if (depth > 2 && inAdrTp && adrTp == null && !value.isBlank()) {
                        adrTp = value.trim(); // AdrTp/Cd, or AdrTp/Prtry/Id: the first leaf value
                    }
                    text.setLength(0);
                    depth--;
                }
                default -> { }
            }
        }

        // Order the fields as the XSD does, with AdrTp first (it comes first in the sequence).
        Map<String, String> ordered = new LinkedHashMap<>();
        if (adrTp != null) {
            ordered.put(PostalAddressSchema.ADDRESS_TYPE, adrTp);
        }
        for (PostalAddressElement e : schema.elements()) {
            if (found.containsKey(e.name())) {
                ordered.put(e.name(), found.get(e.name()));
            }
        }
        return new Candidate(role, rolePath, self.path, List.copyOf(lines), new StructuredAddress(ordered));
    }

    private static void skipRest(SafeXml.Reader in) {
        int depth = 1;
        while (depth > 0) {
            int event = in.next();
            if (event == XMLStreamConstants.START_ELEMENT) {
                depth++;
            } else if (event == XMLStreamConstants.END_ELEMENT) {
                depth--;
            }
        }
    }

    private static String countryHint(Candidate c, Map<String, String> bics) {
        boolean agent = c.role().name().endsWith("_AGENT");
        // 1. The party's own BIC: AnyBIC for parties, BICFI for agents.
        String own = agent
                ? bics.get(c.rolePath() + "/FinInstnId[1]/BICFI[1]")
                : bics.get(c.rolePath() + "/Id[1]/OrgId[1]/AnyBIC[1]");
        String hint = country(own);
        if (hint != null || agent) {
            return hint;
        }
        // 2. The party's bank: walk up from the party to the nearest element that has the matching agent with a BIC.
        String bank = switch (c.role()) {
            case DEBTOR, ULTIMATE_DEBTOR -> "DbtrAgt";
            case CREDITOR, ULTIMATE_CREDITOR -> "CdtrAgt";
            default -> null;
        };
        if (bank == null) {
            return null;
        }
        String container = parent(c.rolePath());
        while (container != null && !container.isEmpty()) {
            String bic = bics.get(container + "/" + bank + "[1]/FinInstnId[1]/BICFI[1]");
            if (bic != null) {
                return country(bic);
            }
            container = parent(container);
        }
        return null;
    }

    private static String country(String bic) {
        if (bic == null || !BIC.matcher(bic).matches()) {
            return null;
        }
        return bic.substring(4, 6);
    }

    private static String parent(String path) {
        int i = path.lastIndexOf('/');
        return i <= 0 ? null : path.substring(0, i);
    }
}
