SET search_path = ag_catalog, "$user", public;

-- 0) Verify that the lookup table is populated
SELECT count(*) FROM ast_edge_guard;

-- 1) Total vertices (AstNode)
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode) RETURN count(n) AS nodes
$$) AS (nodes bigint);

-- 2) Total edges (PARENT_OF)
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH ()-[e:PARENT_OF]->() RETURN count(e) AS edges
$$) AS (edges bigint);

-- 3) Nodes by type (top 20)
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode)
  WITH n.type AS type, count(*) AS cnt
  RETURN type, cnt
  ORDER BY cnt DESC
  LIMIT 20
$$) AS (type text, cnt bigint);

-- 4) Average and max children per parent
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (p:AstNode)-[e:PARENT_OF]->()
  WITH p, count(e) AS outdeg
  RETURN avg(outdeg) AS avg_children, max(outdeg) AS max_children
$$) AS (avg_children numeric, max_children bigint);

-- 5) Heaviest parents (top 10 by out-degree)
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (p:AstNode)-[:PARENT_OF]->()
  WITH p, p.type AS ntype, count(*) AS child_count
  RETURN id(p) AS parent_id, ntype AS type, child_count
  ORDER BY child_count DESC
  LIMIT 10
$$) AS (parent_id bigint, type text, child_count bigint);

-- 6) Leaf nodes (no children)
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode)
  WHERE NOT (n)-[:PARENT_OF]->()
  RETURN count(n) AS leaf_nodes
$$) AS (leaf_nodes bigint);

-- 7) Roots per file (no incoming parent)
SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode)
  WHERE NOT ()-[:PARENT_OF]->(n)
  WITH n.file_uuid AS file_uuid, count(*) AS roots
  RETURN file_uuid, roots
$$) AS (file_uuid text, roots bigint);

-- 8) First N children of a parent (ordered)

SELECT * FROM ag_catalog.cypher(
  'codex_graph',
  $$
    MATCH (p) WHERE id(p) = 1125899906843785 -- <= replace with your parent vertex id()
    MATCH (p)-[e:PARENT_OF]->(c)
    WITH c, e.child_index AS idx
    RETURN id(c) AS child_id, c.type AS type, idx
    ORDER BY idx
    LIMIT 25
  $$
) AS (child_id bigint, type text, idx int);

-- 9) Verify duplicate span_key (should be zero)

SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode)
  WITH n.span_key AS span_key, count(*) AS cnt
  WHERE span_key IS NULL OR cnt > 1
  RETURN span_key, cnt
  ORDER BY cnt DESC
  LIMIT 20
$$) AS (span_key text, cnt bigint);

-- 10) Shape-clone clusters (identical subtrees)

SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode)
  WHERE n.shape_hash IS NOT NULL
  WITH n.shape_hash AS shape_hash,
       collect(DISTINCT n.file_uuid) AS files,
       count(*) AS occurrences
  WHERE size(files) > 1 OR occurrences > 1
  RETURN shape_hash, occurrences, files
  ORDER BY occurrences DESC
  LIMIT 20
$$) AS (shape_hash text, occurrences bigint, files agtype);

-- 11) Per-file counts

SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode)
  WITH n.file_uuid AS file_uuid, count(*) AS nodes
  RETURN file_uuid, nodes
  ORDER BY nodes DESC
  LIMIT 20
$$) AS (file_uuid text, nodes bigint);

-- 12) Nodes by type within one file
-- note: replace file_uuid with the id of the file

SELECT * FROM ag_catalog.cypher('codex_graph', $$
  MATCH (n:AstNode {file_uuid: "9ba28862-2bca-46ea-b95d-b1df103fa053"})
  WITH n.type AS type, count(*) AS cnt
  RETURN type, cnt
  ORDER BY cnt DESC
  LIMIT 10
$$) AS (type text, cnt bigint);
