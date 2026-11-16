-- =====================================================================
-- 04  Migration corridors: account-opening state -> inferred residence
--     ({model} = cri_v1 / cri_atm; {state_col} = its inferred-state column)
-- =====================================================================
WITH m AS (
    SELECT c.customer_id, c.open_state, x.{state_col} AS inferred_state
    FROM customers c JOIN {model} x USING (customer_id)
)
SELECT open_state, inferred_state, COUNT(*) AS customers
FROM m
WHERE open_state <> inferred_state
GROUP BY open_state, inferred_state
ORDER BY customers DESC
