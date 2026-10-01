CREATE CONSTRAINT kr_repository IF NOT EXISTS FOR (n:KRRepository) REQUIRE n.repository_id IS UNIQUE;
CREATE CONSTRAINT kr_generation IF NOT EXISTS FOR (n:KRGeneration) REQUIRE n.key IS UNIQUE;
CREATE CONSTRAINT kr_entity IF NOT EXISTS FOR (n:KREntity) REQUIRE n.key IS UNIQUE;
CREATE INDEX kr_entity_scope IF NOT EXISTS FOR (n:KREntity) ON (n.generation_key, n.canonical_id);
CREATE INDEX kr_entity_kind IF NOT EXISTS FOR (n:KREntity) ON (n.generation_key, n.kind);
