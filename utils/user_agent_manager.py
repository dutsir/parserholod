import random
from typing import List

class UserAgentManager:
    def __init__(self, user_agents: List[str], rotation_enabled: bool = True):
        self.user_agents = [ua for ua in user_agents if ua]
        self.rotation_enabled = rotation_enabled

    def get_user_agent(self) -> str:
        if not self.user_agents:
            return "Mozilla/5.0"
        if not self.rotation_enabled:
            return self.user_agents[0]
        return random.choice(self.user_agents)
