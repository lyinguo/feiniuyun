import unittest

from app.agent.script_graph.workflow import (
    ROUTE_RETRY,
    ROUTE_SUMMARIZE,
    build_script_graph,
    route_after_critic,
)


class ScriptGraphWorkflowTests(unittest.TestCase):
    def test_build_script_graph_compiles(self):
        graph = build_script_graph()
        self.assertIsNotNone(graph)

    def test_route_after_critic_retries_when_error_and_budget_remains(self):
        route = route_after_critic(
            {
                "error_msg": "schema failed",
                "retry_count": 1,
                "max_retries": 3,
            }
        )
        self.assertEqual(route, ROUTE_RETRY)

    def test_route_after_critic_summarizes_when_retry_budget_exhausted(self):
        route = route_after_critic(
            {
                "error_msg": "schema failed",
                "retry_count": 2,
                "max_retries": 2,
            }
        )
        self.assertEqual(route, ROUTE_SUMMARIZE)

    def test_route_after_critic_summarizes_when_no_error(self):
        route = route_after_critic(
            {
                "error_msg": "",
                "retry_count": 0,
                "max_retries": 2,
            }
        )
        self.assertEqual(route, ROUTE_SUMMARIZE)


if __name__ == "__main__":
    unittest.main()

