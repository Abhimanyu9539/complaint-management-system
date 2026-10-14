-- 0027_agent_runs_usage.sql — each ticket-graph run's LLM calls, tokens and cost.
--
-- `cost_usd` is what OpenRouter billed. A call made through another client (NeMo's rails)
-- reports tokens but no cost, so it adds nothing to the total.

ALTER TABLE agent_runs
    ADD COLUMN IF NOT EXISTS llm_calls     JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{node, model, input_tokens, output_tokens, total_tokens, cost_usd}]
    ADD COLUMN IF NOT EXISTS input_tokens  INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS output_tokens INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cost_usd      NUMERIC(14, 8) NOT NULL DEFAULT 0;
