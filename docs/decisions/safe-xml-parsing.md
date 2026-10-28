# Safe XML parsing

Status: accepted (Phase 1)

## Context

Payment messages arrive from outside. Banks test for XML external entity (XXE) attacks, entity-expansion ("billion laughs") and oversized uploads. The spec also wants large batch files read without loading them whole into memory.

## Decision

1. **One factory.** Every StAX reader is created by `SafeXml`: `SUPPORT_DTD=false`, `IS_SUPPORTING_EXTERNAL_ENTITIES=false`, `ACCESS_EXTERNAL_DTD` and `ACCESS_EXTERNAL_SCHEMA` set to empty where supported.
2. **Reject any DOCTYPE outright.** The JDK parser still reports a DTD event when DTD support is off (checked with a probe), although it does not resolve the entity. `SafeXml.Reader.next()` turns that event into HTTP 400 `DTD_NOT_ALLOWED`. A legitimate pacs.008 or pain.001 never needs a DOCTYPE, so refusing is cheaper and clearer than sanitising. An entity reference without a DOCTYPE is an undeclared entity, a fatal parse error, and gives 400 `MALFORMED_XML`.
3. **Detection runs first.** The type-detection pass reads up to the root element, so a DOCTYPE (which must precede the root) is always seen before schema validation starts. The validator is also configured defensively: secure processing, external DTD and schema access empty, and `disallow-doctype-decl` where the JDK supports it.
4. **Cap on the bytes read.** The request body is capped at 5 MB (`paystruct.ingest.max-request-size`). A declared `Content-Length` over the cap is refused immediately; otherwise the cap is enforced while reading, so a chunked upload with no length is stopped too. Both give HTTP 413 `PAYLOAD_TOO_LARGE`. The controller reads the raw request stream rather than letting Spring buffer the body.
5. **Stream from a file.** The body is spooled to a temporary file while its SHA-256 is computed, then detection, validation and extraction each stream that file with StAX or the validator. The message is never held whole in memory, and the temp file is deleted in a `finally`.
6. **Rejected means not stored.** Oversized, DOCTYPE, malformed and unknown-type requests leave no rows.

## Alternatives considered

- Keep DTD parsing on but disable external entities: still exposes entity expansion and leaves more to get wrong.
- Read the body into a `byte[]`: simpler, but defeats streaming and holds up to the cap per request.
- JAXB/DOM for extraction: simpler code, but loads the whole document.

## Consequences

- Tests prove the refusals: an XXE payload (`xxe-payload.xml`) gives 400 and its file target is never read; a body over the cap gives 413 with and without `Content-Length`; nothing is stored in either case.
- The same properties were checked against the running service over real HTTP, not only MockMvc.
- Schema errors are capped at 1,000 recorded per message (`max-schema-errors`); the true count is always reported. This stops a hostile file producing an unbounded error list.
