# PayStruct

Converts free-text postal addresses in ISO 20022 payment messages (pacs.008 and pain.001) into structured address elements, validates the result, and explains failures with a cited rule.

PayStruct implements a documented subset of CBPR+ address rules. It is not certified. All data in this repository is synthetic.

> Status: work in progress. See [docs/PROGRESS.md](docs/PROGRESS.md) for the phase checklist and [docs/spec.md](docs/spec.md) for the full specification.

## Architecture

TODO (Phase 9): architecture diagram and description. Detail is in `docs/spec.md`.

## Results

TODO (Phase 9): the results table is generated from `eval_runs` records. No numbers are written here by hand.

## Run it

Prerequisites: Java 21 and Docker. Maven is not needed; the wrapper is in `service/`.

```bash
cp .env.example .env              # local-only credentials for Docker Compose, gitignored
docker compose up -d --wait       # PostgreSQL 16 (pgvector) and Redis, both with healthchecks
cd service
./mvnw spring-boot:run            # http://localhost:8080
```

That is all. The service connects to the Compose database with built-in local-development defaults (database, user and password are all `paystruct`). Spring Boot does not read `.env`; to point the service somewhere else, set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` in the environment, which override the defaults. If a datasource setting is left unresolved the service refuses to start and says which one.

Try it with the synthetic samples:

```bash
curl -s -H 'Content-Type: application/xml' \
  --data-binary @src/test/resources/samples/pacs008-unstructured.xml \
  http://localhost:8080/v1/messages
curl -s http://localhost:8080/v1/messages/<messageId>
```

Posting the same bytes again returns the stored result with `"duplicate": true`.

## Test

```bash
cd service
./mvnw test       # unit, golden-file and security tests; no Docker needed
./mvnw verify     # also runs the Testcontainers integration test against real PostgreSQL (Docker running)
```

## API (Phase 1)

| Method | Path | Does |
|---|---|---|
| POST | `/v1/messages` | Takes one pacs.008 or pain.001 XML message (`application/xml`), returns the message type, schema errors, whether it is a duplicate, and one address job per party or agent with a postal address |
| GET | `/v1/messages/{id}` | Returns the stored result |

Errors are JSON `{"error": "<CODE>", "message": "..."}`: `DTD_NOT_ALLOWED`, `MALFORMED_XML`, `UNSUPPORTED_MESSAGE_TYPE` (HTTP 400), `PAYLOAD_TOO_LARGE` (413), `MESSAGE_NOT_FOUND` (404).

## Repository layout

```
service/        Spring Boot application (ingestion front door)
agent/          Python: rules engine (agent/rules), later the repair agent and MCP server
data/           generator, labelling guide, dataset splits
eval/           evaluation harness and baselines
review-ui/      review screen and demo page
rule-cards/     rule cards for the explanation layer
docs/           spec, progress, decision records
```

## Schemas

The XSDs in `service/src/main/resources/xsd/` are `pacs.008.001.14` and `pain.001.001.13`, taken from the ISO 20022 message definitions published at iso20022.org and downloaded on 28 Oct 2026. They are the source of truth for element names and maximum lengths; see `docs/decisions/xsd-versions.md`.

## Attribution

Town reference data for the rules engine comes from [GeoNames](https://www.geonames.org) (`cities500.txt`, licensed CC BY 4.0). The file is not committed; it is read-only input at `service/src/main/resources/gazetteer/cities500.txt`. GeoNames postal-code data (also CC BY 4.0) was used to build the synthetic splits. The generator and the rules engine both use GeoNames, so town and postcode accuracy on the synthetic splits is optimistic (`docs/decisions/geonames-circularity.md`).

## Rules engine (Day 2)

```bash
/opt/homebrew/bin/python3.12 -m venv agent/.venv && agent/.venv/bin/pip install -r agent/requirements.txt
agent/.venv/bin/python -m pytest agent/tests                    # unit and property tests
agent/.venv/bin/python -m agent.rules.cli --split dev           # rules only; dev or calibration, nothing else
```

Design and caveats: `docs/decisions/rules-engine.md`.

## Repair agent (Day 4)

The model proposes, plain code decides (`docs/decisions/agent.md`, `docs/threat-model.md`). Everything below runs with no API key and no network:

```bash
agent/.venv/bin/python -m pytest agent evals -q                       # scripted fake model; PostgreSQL tests skip without database settings
agent/.venv/bin/python -m agent.repair.worker --source dev --limit 30 --no-llm --memory   # rules + verifier only
set -a; . ./.env; set +a; agent/.venv/bin/python -m agent.db          # create the agent tables (idempotent), then drop --memory above
```

A real run needs `ANTHROPIC_API_KEY` in the environment, a mandatory `--limit`, and prints an estimate first; see the decision record.
