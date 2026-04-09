# Direct test of MaverickSpawner schedule
import sys
sys.path.insert(0, 'D:/Projects/gov_langgraph')

from gov_langgraph.openclaw_integration.maverick_spawner import MaverickSpawner

spawner = MaverickSpawner(config_path="D:/Projects/gov_langgraph/config/agents.yaml")
result = spawner.schedule(
    project_name="Test",
    project_id="test-project-001",
    task_title="Test task",
    task_id="test-task-001",
    current_stage="BA",
)
print("Result:", result)
print("agent_cfg:", spawner.get_agent("viper"))
print("stage BA -> agent:", spawner._agent_for_stage("BA"))
