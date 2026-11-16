-- =====================================================================
-- 03  CRI final design: two INDEPENDENT models, no blending
-- ---------------------------------------------------------------------
--   Branch model -> MOBILITY signal: where the customer is during the day
--                   (work, errands). Answers "which branches should serve them?"
--   ATM model    -> LOCAL CONVENIENCE signal: people withdraw cash near home.
--                   Answers "where do they live?"
-- Each model keeps its own inferred state and confidence tier.
-- =====================================================================
CREATE OR REPLACE TABLE cri_branch AS
WITH r AS (
    SELECT customer_id, state, branch_events AS ev,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY branch_events DESC, state) AS rn,
           SUM(branch_events) OVER (PARTITION BY customer_id) AS total
    FROM state_signals WHERE branch_events > 0
)
SELECT customer_id, state AS branch_state, ev * 1.0 / total AS branch_share, total AS branch_evidence,
       CASE WHEN ev * 1.0 / total >= 0.6 AND total >= 4 THEN 'HIGH'
            WHEN ev * 1.0 / total >= 0.45 AND total >= 2 THEN 'MEDIUM' ELSE 'LOW' END AS branch_confidence
FROM r WHERE rn = 1;

CREATE OR REPLACE TABLE cri_atm AS
WITH r AS (
    SELECT customer_id, state, atm_events AS ev,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY atm_events DESC, state) AS rn,
           SUM(atm_events) OVER (PARTITION BY customer_id) AS total
    FROM state_signals WHERE atm_events > 0
)
SELECT customer_id, state AS atm_state, ev * 1.0 / total AS atm_share, total AS atm_evidence,
       CASE WHEN ev * 1.0 / total >= 0.6 AND total >= 8 THEN 'HIGH'
            WHEN ev * 1.0 / total >= 0.45 AND total >= 4 THEN 'MEDIUM' ELSE 'LOW' END AS atm_confidence
FROM r WHERE rn = 1;
