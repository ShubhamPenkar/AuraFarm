import inspect
from kaggle_environments.envs.kaggriculture import kaggriculture

lines = inspect.getsourcelines(kaggriculture)[0]
print("All ops in unit step:")
for i, l in enumerate(lines):
    if 'op == ' in l:
        print(f"{i+1}: {l.strip()}")
