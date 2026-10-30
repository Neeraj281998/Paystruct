from agent.db.connection import apply_schema, connect

if __name__ == "__main__":
    with connect() as conn:
        apply_schema(conn)
    print("agent schema applied (idempotent)")
