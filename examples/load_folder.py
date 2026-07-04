from pathlib import Path

from yoke import load

agent = load(Path(__file__).parent / "folder_agent")
print(agent)
