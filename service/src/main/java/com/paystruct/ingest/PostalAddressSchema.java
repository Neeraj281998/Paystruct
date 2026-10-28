package com.paystruct.ingest;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

/**
 * Element names, order, cardinality and maximum lengths of the postal address type, read from the XSD
 * itself. The XSD is the source of truth (see docs/decisions/xsd-versions.md); nothing here is hard-coded
 * from the spec table.
 */
public final class PostalAddressSchema {

    public static final String ADDRESS_LINE = "AdrLine";
    public static final String ADDRESS_TYPE = "AdrTp";

    private static final String XS = XMLConstants.W3C_XML_SCHEMA_NS_URI;

    private final String typeName;
    private final Map<String, PostalAddressElement> elements;

    private PostalAddressSchema(String typeName, Map<String, PostalAddressElement> elements) {
        this.typeName = typeName;
        this.elements = elements;
    }

    /** The XSD type name, for example PostalAddress27. */
    public String typeName() {
        return typeName;
    }

    /** Elements in XSD sequence order. */
    public List<PostalAddressElement> elements() {
        return List.copyOf(elements.values());
    }

    public Optional<PostalAddressElement> element(String name) {
        return Optional.ofNullable(elements.get(name));
    }

    /** True for a simple element that holds one structured value (everything except AdrLine and AdrTp). */
    public boolean isDiscreteField(String name) {
        PostalAddressElement e = elements.get(name);
        return e != null && !e.complex() && !ADDRESS_LINE.equals(name);
    }

    public static PostalAddressSchema load(InputStream xsd) {
        Document doc = parse(xsd);
        Map<String, Element> complexTypes = new LinkedHashMap<>();
        Map<String, Element> simpleTypes = new LinkedHashMap<>();
        for (Element child : children(doc.getDocumentElement())) {
            if (isXs(child, "complexType")) {
                complexTypes.put(child.getAttribute("name"), child);
            } else if (isXs(child, "simpleType")) {
                simpleTypes.put(child.getAttribute("name"), child);
            }
        }
        String typeName = findAddressTypeName(doc);
        Element complex = complexTypes.get(typeName);
        if (complex == null) {
            throw new IllegalStateException("Postal address type " + typeName + " not found in the XSD");
        }
        Map<String, PostalAddressElement> out = new LinkedHashMap<>();
        Element sequence = children(complex).stream().filter(e -> isXs(e, "sequence")).findFirst()
                .orElseThrow(() -> new IllegalStateException(typeName + " has no sequence"));
        int order = 0;
        for (Element el : children(sequence)) {
            if (!isXs(el, "element")) {
                continue;
            }
            String name = el.getAttribute("name");
            String type = el.getAttribute("type");
            int min = el.hasAttribute("minOccurs") ? Integer.parseInt(el.getAttribute("minOccurs")) : 1;
            String maxAttr = el.hasAttribute("maxOccurs") ? el.getAttribute("maxOccurs") : "1";
            int max = "unbounded".equals(maxAttr) ? -1 : Integer.parseInt(maxAttr);
            boolean isComplex = complexTypes.containsKey(type);
            Integer maxLength = null;
            String pattern = null;
            Element simple = simpleTypes.get(type);
            if (simple != null) {
                Element restriction = children(simple).stream().filter(e -> isXs(e, "restriction")).findFirst().orElse(null);
                if (restriction != null) {
                    for (Element facet : children(restriction)) {
                        if (isXs(facet, "maxLength")) {
                            maxLength = Integer.valueOf(facet.getAttribute("value"));
                        } else if (isXs(facet, "pattern")) {
                            pattern = facet.getAttribute("value");
                        }
                    }
                }
            }
            out.put(name, new PostalAddressElement(name, order++, min, max, maxLength, pattern, isComplex));
        }
        return new PostalAddressSchema(typeName, out);
    }

    /** The type of the first PstlAdr element declared with a PostalAddress* type. */
    private static String findAddressTypeName(Document doc) {
        NodeList all = doc.getElementsByTagNameNS(XS, "element");
        for (int i = 0; i < all.getLength(); i++) {
            Element e = (Element) all.item(i);
            if ("PstlAdr".equals(e.getAttribute("name")) && e.getAttribute("type").startsWith("PostalAddress")) {
                return e.getAttribute("type");
            }
        }
        throw new IllegalStateException("No PstlAdr element with a PostalAddress type in the XSD");
    }

    private static Document parse(InputStream xsd) {
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setNamespaceAware(true);
            f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            f.setExpandEntityReferences(false);
            return f.newDocumentBuilder().parse(xsd);
        } catch (ParserConfigurationException | SAXException | IOException e) {
            throw new IllegalStateException("Cannot read the XSD", e);
        }
    }

    private static List<Element> children(Element parent) {
        List<Element> out = new ArrayList<>();
        for (Node n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element e) {
                out.add(e);
            }
        }
        return out;
    }

    private static boolean isXs(Element e, String localName) {
        return XS.equals(e.getNamespaceURI()) && localName.equals(e.getLocalName());
    }
}
