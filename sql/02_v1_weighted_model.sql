-- =====================================================================
-- 02  CRI V1: one blended, weighted model
-- ---------------------------------------------------------------------
-- state score = 2 x branch visits + 1 x card/POS events
-- Inferred state = highest score. Confidence comes from the winning state's
-- share of the total score and the volume of evidence.
-- Kept for comparison: blending a mobility signal (branch) with a
-- spending signal (POS) mislabels commuters.
-- =====================================================================
CREATE OR REPLACE TABLE cri_v1 AS
WITH s AS (
    SELECT customer_id, state, 2 * branch_events + pos_events AS score
    FROM state_signals
),
r AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY score DESC, state) AS rn,
              SUM(score) OVER (PARTITION BY customer_id) AS total
    FROM s WHERE score > 0
)
SELECT customer_id, state AS inferred_state, score * 1.0 / total AS top_share, total AS evidence,
       CASE WHEN score * 1.0 / total >= 0.6 AND total >= 8 THEN 'HIGH'
            WHEN score * 1.0 / total >= 0.45 AND total >= 4 THEN 'MEDIUM' ELSE 'LOW' END AS confidence
FROM r WHERE rn = 1;
