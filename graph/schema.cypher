// Constraints and indexes. Safe to re-run.

CREATE CONSTRAINT source_id   IF NOT EXISTS FOR (s:Source)     REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT concept_code IF NOT EXISTS FOR (c:Concept)   REQUIRE c.code IS UNIQUE;
CREATE CONSTRAINT vocab_name  IF NOT EXISTS FOR (v:Vocabulary) REQUIRE v.name IS UNIQUE;
// Composite uniqueness, not NODE KEY — NODE KEY is Enterprise-only and the
// whole schema file aborts at the first one on Community.
CREATE CONSTRAINT term_key    IF NOT EXISTS FOR (t:Term)       REQUIRE (t.vocabulary, t.value) IS UNIQUE;
CREATE CONSTRAINT deal_name   IF NOT EXISTS FOR (d:Deal)       REQUIRE d.legal_name IS UNIQUE;
CREATE CONSTRAINT fac_code    IF NOT EXISTS FOR (f:Facility)   REQUIRE f.facility_code IS UNIQUE;
CREATE CONSTRAINT cov_code    IF NOT EXISTS FOR (c:Covenant)   REQUIRE c.covenant_code IS UNIQUE;
CREATE CONSTRAINT event_key   IF NOT EXISTS FOR (e:Event)      REQUIRE (e.name, e.date) IS UNIQUE;
CREATE CONSTRAINT seg_key     IF NOT EXISTS FOR (s:Segment)    REQUIRE (s.video_id, s.start) IS UNIQUE;
CREATE CONSTRAINT run_id      IF NOT EXISTS FOR (r:ExtractionRun) REQUIRE r.id IS UNIQUE;

CREATE INDEX obs_concept IF NOT EXISTS FOR (o:Observation) ON (o.concept_code);
CREATE INDEX fact_concept IF NOT EXISTS FOR (f:Fact)       ON (f.concept_code);
CREATE INDEX seg_video   IF NOT EXISTS FOR (s:Segment)     ON (s.video_id);
