-- =====================================================================
-- 01  Location signals: events per customer x state x channel (12 months)
-- =====================================================================
CREATE OR REPLACE TABLE state_signals AS
SELECT customer_id, state,
       SUM(CASE WHEN channel = 'BRANCH' THEN n_events ELSE 0 END) AS branch_events,
       SUM(CASE WHEN channel = 'ATM'    THEN n_events ELSE 0 END) AS atm_events,
       SUM(CASE WHEN channel = 'POS'    THEN n_events ELSE 0 END) AS pos_events
FROM events
WHERE month_idx BETWEEN 0 AND 11
GROUP BY customer_id, state;
