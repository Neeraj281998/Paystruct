# Maven with the wrapper

Status: accepted (Phase 1)

## Context

The service is Java 21 and Spring Boot 3. The build must generate JAXB classes from the two XSDs (jakarta namespace), run unit tests, and run Testcontainers integration tests in CI later.

## Decision

Maven, with the Maven Wrapper (`service/mvnw`, pinned to Maven 3.9.11), and `spring-boot-starter-parent` 3.5.6 as the parent.

- Why Maven: the Spring Boot parent manages dependency versions, `xjc` has a mature Maven plugin (`org.jvnet.jaxb:jaxb-maven-plugin`, jakarta-based), and the build is plain declarative XML that a reviewer at a bank recognises. Gradle would work too; nothing here needs its flexibility.
- Why the wrapper: anyone runs `./mvnw` with no Maven install, and CI uses the same Maven version as a laptop.
- xjc: one execution per XSD, each into its own package (`com.paystruct.xml.pacs008`, `com.paystruct.xml.pain001`), so the two `Document` trees do not collide. Generated sources live in `target/` and are not committed. A new message version means a new execution and a new package.
- Test split: `*Test` classes run under `./mvnw test` with no Docker; `*IT` classes (Testcontainers, real Postgres) run under `./mvnw verify` via Failsafe. This keeps the fast loop Docker-free and matches the CI order in the spec.
- Testcontainers is pinned to 1.21.4, one patch above what Boot 3.5.6 manages (1.21.3). 1.21.3's Docker client gets HTTP 400 from Docker Engine 29 ("Could not find a valid Docker environment"). Remove the override once Boot's managed version includes the fix.

## Consequences

- The build needs network access to Maven Central on first run.
- The JAXB classes are generated and tested against the samples, but ingestion itself reads messages with StAX (see `safe-xml-parsing.md`); JAXB is for typed rebuilding of messages in a later phase.
