"""Проверка «проводки» агента с поддельным LLM-клиентом (без сети)."""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import agent

def blk(**k): return types.SimpleNamespace(**k)

class FakeClient:
    def __init__(self): self.calls = []; self.messages = self
    def create(self, **kw):
        self.calls.append(kw)
        n = len(self.calls)
        if n == 1:
            return blk(stop_reason="tool_use", content=[blk(type="tool_use", id="t1", name="search_entity",
                       input={"kind": "product", "query": "paxta"}),
                       blk(type="tool_use", id="t2", name="run_sql",
                       input={"query": "SELECT year, COUNT(*) n FROM v_deals WHERE product_code='520100' GROUP BY year"})])
        return blk(stop_reason="end_turn", content=[blk(type="text", text="ok: tool results received")])

fc = FakeClient()
r = agent.ask("2024-yilda paxta bitimlari soni?", client=fc)
assert r["answer"].startswith("ok"), r
assert [t["tool"] for t in r["trace"]] == ["search_entity", "run_sql"]
assert r["trace"][1]["output"]["row_count"] == 5, r["trace"][1]
last = fc.calls[1]["messages"][-1]["content"]
assert last[0]["tool_use_id"] == "t1" and last[1]["tool_use_id"] == "t2"
print("flow OK;", r["steps"], "steps;", r["trace"][1]["output"]["rows"])
